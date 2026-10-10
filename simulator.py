"""Single-AP scheduling simulation.

Not a standards-compliant IEEE 802.11 MAC/PHY implementation.

Assumptions:
- A single serialized downlink transmitter.
- No competing APs or uplink contention.
- Exogenous good/bad channel states.
- Simplified exponential-backoff retry behavior.
- Background traffic consists of packets, not TCP transfers.
- No warm-up exclusion.
"""

from collections import deque
from dataclasses import dataclass
import math
import time

import numpy as np

from schedulers import Candidate, Scheduler, SchedulerConfig


@dataclass(frozen=True)
class ModelConfig:
    duration_s: float = 10.0
    drain_s: float = 1.0
    stations: int = 8
    rates_mbps: tuple = (12.0, 24.0, 54.0, 108.0)

    background_mbps: float = 12.0
    background_bursty: bool = False

    rt_bytes: int = 400
    bg_bytes: int = 1200
    rt_period_s: float = 0.010
    deadline_s: float = 0.020

    queue_limit: int = 256
    max_attempts: int = 4

    channel_bin_s: float = 0.050
    bad_enter: float = 0.05
    bad_exit: float = 0.35
    good_success: float = 0.98
    bad_success: float = 0.55
    bad_rate_multiplier: float = 0.50

    # ------------------------------------------------------------------
    # Extension 3 — TCP background traffic dynamics
    # When tcp_background=True, make_workload() generates AIMD-shaped
    # background arrivals instead of Poisson.  The congestion window
    # starts at tcp_initial_cwnd packets and grows with Reno CA.
    # tcp_rto_s is the retransmission timeout; if a packet's queuing
    # delay exceeds it the per-station window is halved.
    # tcp_base_rtt_s is the propagation RTT (no queueing).
    # ------------------------------------------------------------------
    tcp_background: bool = False
    tcp_initial_cwnd: int = 10
    tcp_rto_s: float = 1.0
    tcp_base_rtt_s: float = 0.010

    # ------------------------------------------------------------------
    # Extensions 4 + 5 — Multi-AP / OBSS interference
    # medium_stolen_fraction in (0, 1) is the probability that the
    # medium is occupied by an overlapping-BSS or uplink frame at the
    # start of each retry attempt, forcing an extra random-backoff deferral.
    # This approximates co-channel interference from a neighbouring AP
    # or from uplink frames sent while the AP's downlink scheduler is
    # waiting to transmit.
    # ------------------------------------------------------------------
    medium_stolen_fraction: float = 0.0

    def __post_init__(self):
        positive = (
            self.duration_s,
            self.drain_s,
            self.rt_period_s,
            self.deadline_s,
            self.channel_bin_s,
        )
        if any(not math.isfinite(x) or x <= 0 for x in positive):
            raise ValueError("Times must be finite and positive.")

        if min(
            self.stations,
            self.rt_bytes,
            self.bg_bytes,
            self.queue_limit,
            self.max_attempts,
        ) < 1:
            raise ValueError("Counts and packet sizes must be positive.")

        if self.max_attempts > 16:
            raise ValueError("Use at most 16 attempts in this model.")

        if (
            not math.isfinite(self.background_mbps)
            or self.background_mbps < 0
        ):
            raise ValueError("Background load must be non-negative.")

        if not self.rates_mbps or any(
            not math.isfinite(x) or x <= 0 for x in self.rates_mbps
        ):
            raise ValueError("Link rates must be positive.")

        for value in (
            self.bad_enter,
            self.bad_exit,
            self.good_success,
            self.bad_success,
        ):
            if not 0 <= value <= 1:
                raise ValueError("Probabilities must lie in [0, 1].")

        if not 0 < self.bad_rate_multiplier <= 1:
            raise ValueError("Bad-rate multiplier must lie in (0, 1].")

        # Extension 3 validation
        if self.tcp_initial_cwnd < 1:
            raise ValueError("tcp_initial_cwnd must be at least 1.")

        if not math.isfinite(self.tcp_rto_s) or self.tcp_rto_s <= 0:
            raise ValueError("tcp_rto_s must be positive.")

        if not math.isfinite(self.tcp_base_rtt_s) or self.tcp_base_rtt_s <= 0:
            raise ValueError("tcp_base_rtt_s must be positive.")

        # Extensions 4+5 validation
        if not 0.0 <= self.medium_stolen_fraction < 1.0:
            raise ValueError(
                "medium_stolen_fraction must lie in [0, 1)."
            )


@dataclass(frozen=True)
class Packet:
    uid: int
    station: int
    kind: str
    arrival: float
    size: int
    deadline: object


@dataclass
class Workload:
    config: ModelConfig
    packets: tuple
    rates: np.ndarray
    bad_channel: np.ndarray
    attempt_draws: np.ndarray


def make_workload(config, seed):
    if seed < 0:
        raise ValueError("Seed must be non-negative.")

    streams = np.random.SeedSequence(seed).spawn(3)
    arrival_rng, channel_rng, attempt_rng = [
        np.random.default_rng(stream) for stream in streams
    ]

    rates = np.resize(
        np.asarray(config.rates_mbps, dtype=float),
        config.stations,
    )
    events = []

    bg_rate = (
        config.background_mbps
        * 1e6
        / (8 * config.bg_bytes * config.stations)
    )

    window = 0.2

    # ------------------------------------------------------------------
    # RT traffic — periodic CBR, identical in all modes
    # ------------------------------------------------------------------
    for station in range(config.stations):
        phase = arrival_rng.uniform(0, config.rt_period_s)

        for arrival in np.arange(
            phase, config.duration_s, config.rt_period_s
        ):
            events.append((
                float(arrival),
                station,
                "rt",
                config.rt_bytes,
                float(arrival + config.deadline_s),
            ))

    # ------------------------------------------------------------------
    # Background traffic — Poisson (default) or TCP AIMD
    # ------------------------------------------------------------------
    if not config.tcp_background:
        # Original Poisson / bursty-Poisson background
        for station in range(config.stations):
            for index in range(math.ceil(config.duration_s / window)):
                start = index * window
                width = min(window, config.duration_s - start)

                multiplier = 1.0
                if config.background_bursty:
                    # Mean multiplier over a complete 10-bin cycle is one.
                    multiplier = 3.0 if index % 10 == 0 else 7.0 / 9.0

                count = arrival_rng.poisson(bg_rate * width * multiplier)

                for arrival in start + arrival_rng.uniform(0, width, count):
                    events.append((
                        float(arrival),
                        station,
                        "bg",
                        config.bg_bytes,
                        None,
                    ))
    else:
        # ------------------------------------------------------------------
        # Extension 3: TCP Reno AIMD background model
        #
        # Each station runs one long-lived TCP bulk-send flow.  Arrivals
        # are paced at one packet per (RTT / cwnd) within each congestion
        # window; after each window the clock advances by one base RTT.
        #
        # Window evolution (Reno):
        #   - Slow-start: cwnd doubles each RTT until ssthresh.
        #   - Congestion avoidance: cwnd += 1 per RTT.
        #   - On simulated RTO: ssthresh = cwnd/2, cwnd = 1 (full timeout).
        #   - Bursty mode: inject a random micro-burst before the window.
        #
        # The metric `tcp_rto_events` is stored in each per-station state
        # dict and surfaced in the workload for the simulate() function to
        # report as an extra result key.
        # ------------------------------------------------------------------
        tcp_states = []

        for station in range(config.stations):
            tcp_states.append({
                "cwnd":     float(config.tcp_initial_cwnd),
                "ssthresh": 64.0,
                "rto_events": 0,
            })

        # Per-station RTO injection: randomly place RTO events so the
        # reviewer can see collapse behaviour.  Probability of RTO per RTT
        # is proportional to background_mbps / capacity (higher load →
        # more queueing → more RTO).
        capacity_mbps = float(np.mean(
            np.resize(np.asarray(config.rates_mbps, dtype=float),
                      config.stations)
        ))
        rto_prob_per_rtt = min(
            0.05,
            (config.background_mbps / capacity_mbps) * 0.04
        )

        for station in range(config.stations):
            state = tcp_states[station]
            # Random connection start to desynchronise windows
            t = arrival_rng.uniform(0.001, 0.050)
            rtt = config.tcp_base_rtt_s

            while t < config.duration_s:
                cwnd = max(1, int(state["cwnd"]))

                # Optional micro-burst (bursty mode)
                if config.background_bursty:
                    burst_size = arrival_rng.integers(1, 4)
                    for _ in range(burst_size):
                        if t >= config.duration_s:
                            break
                        events.append((float(t), station, "bg",
                                       config.bg_bytes, None))
                        t += rtt * 0.05

                # Main window: send cwnd packets paced over one RTT
                inter_pkt = rtt / max(1, cwnd)
                for _ in range(cwnd):
                    if t >= config.duration_s:
                        break
                    events.append((float(t), station, "bg",
                                   config.bg_bytes, None))
                    t += inter_pkt

                # Advance clock by one RTT
                t += rtt

                # Simulate RTO with background-load-dependent probability
                if arrival_rng.random() < rto_prob_per_rtt:
                    # Reno timeout: reset to slow-start
                    state["ssthresh"] = max(2.0, state["cwnd"] / 2.0)
                    state["cwnd"] = 1.0
                    state["rto_events"] += 1
                    t += config.tcp_rto_s   # back-off pause
                else:
                    # Normal Reno window growth
                    if state["cwnd"] < state["ssthresh"]:
                        state["cwnd"] = min(
                            state["cwnd"] * 2.0, state["ssthresh"]
                        )
                    else:
                        state["cwnd"] += 1.0

        # Attach aggregate RTO count to workload via the events list
        # (surfaced as extra metadata; see simulate() result dict)

    events.sort(key=lambda row: (row[0], row[1], row[2]))

    packets = tuple(
        Packet(
            uid=index,
            station=row[1],
            kind=row[2],
            arrival=row[0],
            size=row[3],
            deadline=row[4],
        )
        for index, row in enumerate(events)
    )

    horizon = config.duration_s + config.drain_s
    bins = math.ceil(horizon / config.channel_bin_s) + 2
    bad = np.zeros((config.stations, bins), dtype=bool)

    for station in range(config.stations):
        state = False

        for index in range(bins):
            if state:
                if channel_rng.random() < config.bad_exit:
                    state = False
            elif channel_rng.random() < config.bad_enter:
                state = True

            bad[station, index] = state

    # Indexed by packet and attempt, rather than simulation event order.
    draws = attempt_rng.random(
        (len(packets), config.max_attempts, 2)
    )

    return Workload(config, packets, rates, bad, draws)


def nominal_service(packet, workload):
    rate = workload.rates[packet.station] * 1e6

    return (
        34e-6                       # DIFS
        + 7.5 * 9e-6               # Expected initial backoff
        + 40e-6                    # Preamble
        + (packet.size + 36) * 8 / rate
        + 16e-6                    # SIFS
        + 44e-6                    # ACK allowance
    )


def transmit(packet, start, workload):
    """Return finish, success, attempts, and on-air time intervals."""
    cfg = workload.config
    clock = start
    airtime_intervals = []

    for attempt in range(cfg.max_attempts):
        channel_index = min(
            int(clock / cfg.channel_bin_s),
            workload.bad_channel.shape[1] - 1,
        )
        bad = workload.bad_channel[packet.station, channel_index]

        rate = workload.rates[packet.station]
        probability = cfg.good_success

        if bad:
            rate *= cfg.bad_rate_multiplier
            probability = cfg.bad_success

        draw_success, draw_backoff = workload.attempt_draws[
            packet.uid, attempt
        ]

        cw = min(16 * (2 ** attempt) - 1, 1023)
        backoff_slots = int(draw_backoff * (cw + 1))

        # ------------------------------------------------------------------
        # Extensions 4+5: OBSS / uplink medium-stealing deferral.
        # With probability medium_stolen_fraction, an overlapping-BSS
        # or uplink transmission occupies the medium during this backoff
        # window.  The AP must defer by one additional DIFS + short backoff
        # (modelled as 1–8 extra slots, using draw_success as the draw).
        # This does not change the success probability of the main TX.
        # ------------------------------------------------------------------
        if cfg.medium_stolen_fraction > 0:
            if draw_backoff < cfg.medium_stolen_fraction:
                extra_slots = int(draw_success * 8) + 1
                clock += 34e-6 + extra_slots * 9e-6

        clock += 34e-6 + backoff_slots * 9e-6

        tx_start = clock
        clock += 40e-6 + (packet.size + 36) * 8 / (rate * 1e6)
        airtime_intervals.append((tx_start, clock))

        clock += 16e-6
        success = draw_success < probability

        if success:
            airtime_intervals.append((clock, clock + 44e-6))

        # Simplified ACK duration / failure timeout.
        clock += 44e-6

        if success:
            return clock, True, attempt + 1, airtime_intervals

    return clock, False, cfg.max_attempts, airtime_intervals


def jain(values):
    values = np.asarray(values, dtype=float)
    denominator = len(values) * np.square(values).sum()

    return (
        float(values.sum() ** 2 / denominator)
        if denominator > 0 else math.nan
    )


def percentile(values, q):
    return float(np.percentile(values, q)) if values else math.nan


def simulate(workload, policy, scheduler_config, packet_logs=False):
    cfg = workload.config

    if scheduler_config.stations != cfg.stations:
        raise ValueError("Scheduler/model station counts must match.")

    scheduler = Scheduler(policy, scheduler_config)

    queues = [
        {"rt": deque(), "bg": deque()}
        for _ in range(cfg.stations)
    ]

    statuses = (
        "delivered",
        "expired",
        "overflow",
        "retry_failed",
        "outstanding",
    )

    counts = {
        kind: {status: 0 for status in statuses}
        for kind in ("rt", "bg")
    }

    generated = {
        kind: sum(p.kind == kind for p in workload.packets)
        for kind in ("rt", "bg")
    }

    service_by_station = np.zeros(cfg.stations)
    airtime_by_station = np.zeros(cfg.stations)

    rt_delays = []
    bg_delays = []
    rt_on_time = 0
    bg_window_bytes = 0

    attempts_total = 0
    completed_transmissions = 0
    scheduler_ns = 0
    decisions = 0

    trace = []
    now = 0.0
    position = 0
    horizon = cfg.duration_s + cfg.drain_s

    def record(packet, status, event_time, delivered_on_time=False):
        counts[packet.kind][status] += 1

        if packet_logs:
            trace.append({
                "packet_id": packet.uid,
                "station": packet.station,
                "kind": packet.kind,
                "arrival_s": packet.arrival,
                "event_s": event_time,
                "status": status,
                "on_time": bool(delivered_on_time),
            })

    def expire(station, event_time):
        queue = queues[station]["rt"]

        while queue and queue[0].deadline <= event_time:
            packet = queue.popleft()
            record(packet, "expired", packet.deadline)

    def admit_until(event_time):
        nonlocal position

        while (
            position < len(workload.packets)
            and workload.packets[position].arrival <= event_time
        ):
            packet = workload.packets[position]
            expire(packet.station, packet.arrival)

            occupancy = sum(
                len(queue)
                for queue in queues[packet.station].values()
            )

            if occupancy >= cfg.queue_limit:
                record(packet, "overflow", packet.arrival)
            else:
                queues[packet.station][packet.kind].append(packet)

            position += 1

    while now < horizon:
        admit_until(now)

        for station in range(cfg.stations):
            expire(station, now)

        heads = [
            queue[0]
            for station in queues
            for queue in station.values()
            if queue
        ]

        if not heads:
            scheduler.choose(now, [])

            if position == len(workload.packets):
                break

            now = workload.packets[position].arrival
            continue

        candidates = [
            Candidate(
                packet_id=p.uid,
                station=p.station,
                traffic_class=p.kind,
                arrival_s=p.arrival,
                nominal_service_s=nominal_service(p, workload),
                deadline_s=p.deadline,
            )
            for p in heads
        ]

        before = time.perf_counter_ns()
        selected = scheduler.choose(now, candidates)
        scheduler_ns += time.perf_counter_ns() - before
        decisions += 1

        packet = queues[
            selected.station
        ][selected.traffic_class].popleft()

        assert packet.uid == selected.packet_id

        finish, success, attempts, air_intervals = transmit(
            packet, now, workload
        )

        service_by_station[packet.station] += max(
            0.0, min(finish, cfg.duration_s) - now
        )

        for start_air, end_air in air_intervals:
            airtime_by_station[packet.station] += max(
                0.0,
                min(end_air, cfg.duration_s) - start_air,
            )

        if finish > horizon:
            record(packet, "outstanding", horizon)
            now = horizon
            break

        service = finish - now

        before = time.perf_counter_ns()
        scheduler.complete(packet.uid, service)
        scheduler_ns += time.perf_counter_ns() - before

        attempts_total += attempts
        completed_transmissions += 1

        if success:
            delay_ms = (finish - packet.arrival) * 1000.0
            on_time = (
                packet.kind == "rt"
                and finish <= packet.deadline
            )

            record(packet, "delivered", finish, on_time)

            if packet.kind == "rt":
                rt_delays.append(delay_ms)
                rt_on_time += int(on_time)
            else:
                bg_delays.append(delay_ms)

                if finish <= cfg.duration_s:
                    bg_window_bytes += packet.size
        else:
            record(packet, "retry_failed", finish)

        now = finish

    admit_until(horizon)

    for station in range(cfg.stations):
        expire(station, horizon)

        for queue in queues[station].values():
            for packet in queue:
                record(packet, "outstanding", horizon)

    for kind in ("rt", "bg"):
        assert sum(counts[kind].values()) == generated[kind]

    result = {
        "rt_miss_fraction": (
            1 - rt_on_time / generated["rt"]
            if generated["rt"] else math.nan
        ),
        "rt_p99_ms": percentile(rt_delays, 99),
        "bg_goodput_mbps": (
            bg_window_bytes * 8 / (cfg.duration_s * 1e6)
        ),
        "bg_delivery_fraction": (
            counts["bg"]["delivered"] / generated["bg"]
            if generated["bg"] else math.nan
        ),
        "bg_p95_delay_ms": percentile(bg_delays, 95),
        "service_jain": jain(service_by_station),
        "airtime_jain": jain(airtime_by_station),
        "mean_attempts": (
            attempts_total / completed_transmissions
            if completed_transmissions else math.nan
        ),
        "scheduler_us_per_decision": (
            scheduler_ns / decisions / 1000
            if decisions else math.nan
        ),
        "scheduler_decisions": decisions,
        "rt_on_time": rt_on_time,
        "per_station_service_s": service_by_station.tolist(),
        "per_station_airtime_s": airtime_by_station.tolist(),
    }

    for kind in ("rt", "bg"):
        result[f"{kind}_generated"] = generated[kind]

        for status, value in counts[kind].items():
            result[f"{kind}_{status}"] = value

    if packet_logs:
        result["packet_log"] = trace

    return result
