"""
Scheduling policies for a single non-preemptive transmitter.

This file does not simulate Wi-Fi.

Simulator contract
------------------
1. Remove expired packets according to the application's drop policy.
2. Supply one head-of-line Candidate per nonempty station/traffic queue.
3. Call scheduler.choose(now_s, candidates).
4. Transmit the returned packet.
5. Call scheduler.complete(packet_id, measured_service_s), including
   consumed service time even if transmission fails.

All policies receive the same candidate information.

The proposed policy is a research hypothesis, not an established novel
algorithm or a guaranteed improvement over the baselines.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Dict, Optional, Sequence, Tuple


class Policy(str, Enum):
    ROUND_ROBIN = "round_robin"
    EDF = "edf"
    SERVICE_DRR = "service_drr"
    PROPOSED = "proposed"
    NO_URGENCY = "no_urgency"
    NO_FAIRNESS = "no_fairness"
    NO_RETRY_ESTIMATE = "no_retry_estimate"
    EDCA = "edca"


POLICY_NAMES = tuple(policy.value for policy in Policy)


@dataclass(frozen=True)
class Candidate:
    """Head-of-line packet exposed by the simulator."""

    packet_id: int
    station: int
    traffic_class: str       # "rt" or "bg"
    arrival_s: float
    nominal_service_s: float
    deadline_s: Optional[float] = None

    def __post_init__(self):
        if self.packet_id < 0:
            raise ValueError("packet_id must be non-negative.")

        if self.station < 0:
            raise ValueError("station must be non-negative.")

        if self.traffic_class not in {"rt", "bg"}:
            raise ValueError("traffic_class must be 'rt' or 'bg'.")

        if not math.isfinite(self.arrival_s) or self.arrival_s < 0:
            raise ValueError("arrival_s must be finite and non-negative.")

        if (
            not math.isfinite(self.nominal_service_s)
            or self.nominal_service_s <= 0
        ):
            raise ValueError("nominal_service_s must be positive.")

        if self.traffic_class == "rt":
            if (
                self.deadline_s is None
                or not math.isfinite(self.deadline_s)
                or self.deadline_s <= self.arrival_s
            ):
                raise ValueError(
                    "Real-time packets need a finite deadline "
                    "after their arrival."
                )

        elif self.deadline_s is not None:
            raise ValueError(
                "Background packets must have deadline_s=None."
            )


@dataclass(frozen=True)
class SchedulerConfig:
    stations: int = 8

    # DRR quantum and normalization scale for station credit.
    quantum_s: float = 0.001

    # Maximum positive station credit.
    credit_cap_s: float = 0.020

    # Real-time packets within this estimated slack are urgent.
    urgency_horizon_s: float = 0.010

    # Relative strength of station credit in the urgency score.
    fairness_weight: float = 0.25

    # Heuristic share of modeled service reserved for background work.
    background_share: float = 0.20

    # Maximum background service debt.
    background_debt_cap_s: float = 0.020

    # EWMA coefficient for observed/nominal service ratios.
    estimator_alpha: float = 0.20

    def __post_init__(self):
        if self.stations < 1:
            raise ValueError("stations must be positive.")

        positive_parameters = {
            "quantum_s": self.quantum_s,
            "credit_cap_s": self.credit_cap_s,
            "urgency_horizon_s": self.urgency_horizon_s,
            "background_debt_cap_s": self.background_debt_cap_s,
        }

        for name, value in positive_parameters.items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive.")

        if (
            not math.isfinite(self.fairness_weight)
            or self.fairness_weight < 0
        ):
            raise ValueError("fairness_weight must be non-negative.")

        if not 0 <= self.background_share <= 1:
            raise ValueError("background_share must lie in [0, 1].")

        if not 0 < self.estimator_alpha <= 1:
            raise ValueError("estimator_alpha must lie in (0, 1].")


class Scheduler:
    """Common interface for reference policies and ablations."""

    def __init__(
        self,
        policy: str,
        config: Optional[SchedulerConfig] = None,
    ):
        self.policy = Policy(policy)
        self.config = config or SchedulerConfig()

        n = self.config.stations

        self._credit = [0.0] * n
        self._drr_credit = [0.0] * n

        # Separate estimates for each station and traffic class.
        self._service_ratio: Dict[Tuple[int, str], float] = {}

        self._rr_station = 0
        self._drr_station = 0
        self._drr_new_visit = True

        self._background_debt = 0.0

        self._pending: Optional[Candidate] = None
        self._pending_active: Tuple[int, ...] = ()
        self._pending_background = False
        self._pending_start = 0.0

        self._available_at = 0.0

    def estimate(self, packet: Candidate) -> float:
        """Predict service duration using only nominal and past data."""
        if self.policy == Policy.NO_RETRY_ESTIMATE:
            return packet.nominal_service_s

        factor = self._service_ratio.get(
            (packet.station, packet.traffic_class),
            1.0,
        )
        return packet.nominal_service_s * factor

    @staticmethod
    def _oldest(candidates: Sequence[Candidate]) -> Candidate:
        return min(
            candidates,
            key=lambda packet: (packet.arrival_s, packet.packet_id),
        )

    def _validate_candidates(
        self,
        now_s: float,
        candidates: Sequence[Candidate],
    ) -> None:
        if not math.isfinite(now_s) or now_s < 0:
            raise ValueError("now_s must be finite and non-negative.")

        if self._pending is not None:
            raise RuntimeError(
                "complete() must be called before another choose()."
            )

        if now_s + 1e-12 < self._available_at:
            raise ValueError(
                "Cannot schedule before the previous service completes."
            )

        packet_ids = set()
        queue_keys = set()

        for packet in candidates:
            if packet.station >= self.config.stations:
                raise ValueError("Station is outside the configured range.")

            if packet.arrival_s > now_s + 1e-12:
                raise ValueError("Candidate has not arrived yet.")

            if (
                packet.deadline_s is not None
                and packet.deadline_s <= now_s
            ):
                raise ValueError(
                    "Remove expired real-time packets before scheduling."
                )

            if packet.packet_id in packet_ids:
                raise ValueError("Duplicate packet_id.")

            queue_key = (packet.station, packet.traffic_class)

            if queue_key in queue_keys:
                raise ValueError(
                    "Supply only one head-of-line packet per "
                    "station/traffic-class queue."
                )

            packet_ids.add(packet.packet_id)
            queue_keys.add(queue_key)

    def _round_robin(
        self,
        candidates: Sequence[Candidate],
    ) -> Candidate:
        for _ in range(self.config.stations):
            station = self._rr_station
            self._rr_station = (
                self._rr_station + 1
            ) % self.config.stations

            available = [
                packet
                for packet in candidates
                if packet.station == station
            ]

            if available:
                return self._oldest(available)

        raise RuntimeError("No candidate found in round-robin scheduling.")

    def _service_drr(
        self,
        candidates: Sequence[Candidate],
    ) -> Candidate:
        by_station = {
            station: [
                packet
                for packet in candidates
                if packet.station == station
            ]
            for station in range(self.config.stations)
        }

        # Positive quantum ensures eventual eligibility.
        # Actual service can exceed the estimate; the resulting negative
        # deficit carries forward to subsequent visits.
        while True:
            station = self._drr_station
            available = by_station[station]

            if not available:
                self._drr_credit[station] = 0.0
                self._drr_station = (
                    station + 1
                ) % self.config.stations
                self._drr_new_visit = True
                continue

            if self._drr_new_visit:
                self._drr_credit[station] += self.config.quantum_s
                self._drr_new_visit = False

            packet = self._oldest(available)

            if self._drr_credit[station] >= self.estimate(packet):
                return packet

            self._drr_station = (
                station + 1
            ) % self.config.stations
            self._drr_new_visit = True

    def _edca(
        self,
        candidates: Sequence[Candidate],
    ) -> Candidate:
        """IEEE 802.11e EDCA: strict Access-Category priority, FIFO within AC.

        Traffic-class mapping (conservative / strong baseline):
            rt  → AC_VI  (Video, AIFSN=2, CW_min=7)  — priority 0
            bg  → AC_BE  (Best Effort, AIFSN=3, CW_min=15) — priority 1

        This gives EDCA the benefit of strict priority without modelling
        CSMA/CA overhead or per-station fairness, making it a tough
        comparison point. If U-AFS still wins on fairness metrics, the
        claim is stronger.
        """
        AC_PRIORITY = {"rt": 0, "bg": 1}
        return min(
            candidates,
            key=lambda p: (
                AC_PRIORITY[p.traffic_class],
                p.arrival_s,
                p.packet_id,
            ),
        )

    def _proposed_family(
        self,
        now_s: float,
        candidates: Sequence[Candidate],
    ) -> Candidate:
        fairness_enabled = self.policy != Policy.NO_FAIRNESS
        urgency_enabled = self.policy != Policy.NO_URGENCY

        def fairness_key(packet):
            return (
                -self._credit[packet.station]
                if fairness_enabled
                else 0.0,
                packet.arrival_s,
                packet.packet_id,
            )

        background = [
            packet
            for packet in candidates
            if packet.traffic_class == "bg"
        ]

        # Background reservation is based on outstanding service debt.
        # It is intentionally described as a heuristic, not a guarantee.
        if background:
            next_background = min(background, key=fairness_key)

            if self._background_debt >= self.estimate(next_background):
                return next_background

        urgent = []

        if urgency_enabled:
            for packet in candidates:
                if packet.traffic_class != "rt":
                    continue

                slack = (
                    packet.deadline_s
                    - now_s
                    - self.estimate(packet)
                )

                # Predicted-infeasible packets are not called urgent.
                # They remain eligible for fallback selection; the
                # simulator handles actual deadline expiry separately.
                if 0 <= slack <= self.config.urgency_horizon_s:
                    score = (
                        slack / self.config.urgency_horizon_s
                    )

                    if fairness_enabled:
                        score -= (
                            self.config.fairness_weight
                            * self._credit[packet.station]
                            / self.config.quantum_s
                        )

                    urgent.append(
                        (score, packet.arrival_s, packet.packet_id, packet)
                    )

        if urgent:
            return min(urgent, key=lambda entry: entry[:3])[3]

        return min(candidates, key=fairness_key)

    def choose(
        self,
        now_s: float,
        candidates: Sequence[Candidate],
    ) -> Optional[Candidate]:
        candidates = tuple(candidates)
        self._validate_candidates(now_s, candidates)

        active = tuple(sorted({
            packet.station for packet in candidates
        }))

        # Do not allow an inactive station to accumulate credit forever.
        for station in range(self.config.stations):
            if station not in active:
                self._credit[station] = 0.0
                self._drr_credit[station] = 0.0

        if not candidates:
            self._background_debt = 0.0
            self._available_at = now_s
            return None

        background_waiting = any(
            packet.traffic_class == "bg"
            for packet in candidates
        )

        if not background_waiting:
            self._background_debt = 0.0

        if self.policy == Policy.ROUND_ROBIN:
            selected = self._round_robin(candidates)

        elif self.policy == Policy.EDF:
            selected = min(
                candidates,
                key=lambda packet: (
                    (
                        packet.deadline_s
                        if packet.deadline_s is not None
                        else math.inf
                    ),
                    packet.arrival_s,
                    packet.packet_id,
                ),
            )

        elif self.policy == Policy.SERVICE_DRR:
            selected = self._service_drr(candidates)

        elif self.policy == Policy.EDCA:
            selected = self._edca(candidates)

        else:
            selected = self._proposed_family(now_s, candidates)

        self._pending = selected
        self._pending_active = active
        self._pending_background = background_waiting
        self._pending_start = now_s

        return selected

    def complete(
        self,
        packet_id: int,
        measured_service_s: float,
    ) -> None:
        """Account for completed or failed transmission service.

        Call this for failed transmissions too: they still consume time.
        Packet delivery success is tracked by the simulator, not here.
        """
        if self._pending is None:
            raise RuntimeError("No scheduled packet awaiting completion.")

        if packet_id != self._pending.packet_id:
            raise ValueError("Completion packet_id does not match selection.")

        if (
            not math.isfinite(measured_service_s)
            or measured_service_s <= 0
        ):
            raise ValueError("measured_service_s must be positive.")

        packet = self._pending

        # Share credits among stations active when this service began.
        # This is a discrete scheduling approximation.
        increment = measured_service_s / len(self._pending_active)

        for station in self._pending_active:
            self._credit[station] = min(
                self.config.credit_cap_s,
                self._credit[station] + increment,
            )

        self._credit[packet.station] -= measured_service_s
        self._drr_credit[packet.station] -= measured_service_s

        if self._pending_background:
            self._background_debt += (
                self.config.background_share * measured_service_s
            )

            if packet.traffic_class == "bg":
                self._background_debt -= measured_service_s

            self._background_debt = min(
                self.config.background_debt_cap_s,
                max(0.0, self._background_debt),
            )
        else:
            self._background_debt = 0.0

        key = (packet.station, packet.traffic_class)
        previous = self._service_ratio.get(key, 1.0)
        observed = measured_service_s / packet.nominal_service_s
        alpha = self.config.estimator_alpha

        self._service_ratio[key] = (
            (1.0 - alpha) * previous + alpha * observed
        )

        self._available_at = (
            self._pending_start + measured_service_s
        )

        self._pending = None
        self._pending_active = ()
        self._pending_background = False

    def diagnostics(self) -> dict:
        """Return a copy of internal state for tests and optional tracing."""
        return {
            "policy": self.policy.value,
            "station_credit_s": list(self._credit),
            "drr_credit_s": list(self._drr_credit),
            "background_debt_s": self._background_debt,
            "service_ratios": dict(self._service_ratio),
            "available_at_s": self._available_at,
            "pending_packet_id": (
                self._pending.packet_id
                if self._pending is not None
                else None
            ),
        }
