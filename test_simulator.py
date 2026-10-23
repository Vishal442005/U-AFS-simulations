import math
import unittest

from schedulers import POLICY_NAMES, SchedulerConfig
from simulator import ModelConfig, make_workload, simulate


class SimulatorTests(unittest.TestCase):
    def config(self):
        return ModelConfig(
            duration_s=0.3,
            drain_s=0.3,
            stations=3,
            background_mbps=2.0,
        )

    def test_all_policies_conserve_packets(self):
        config = self.config()
        workload = make_workload(config, seed=17)
        scheduler = SchedulerConfig(stations=config.stations)

        for policy in POLICY_NAMES:
            with self.subTest(policy=policy):
                result = simulate(workload, policy, scheduler)

                for kind in ("rt", "bg"):
                    total = sum(
                        result[f"{kind}_{status}"]
                        for status in (
                            "delivered",
                            "expired",
                            "overflow",
                            "retry_failed",
                            "outstanding",
                        )
                    )
                    self.assertEqual(
                        total, result[f"{kind}_generated"]
                    )

                for metric in (
                    "rt_miss_fraction",
                    "bg_delivery_fraction",
                    "service_jain",
                    "airtime_jain",
                ):
                    self.assertGreaterEqual(result[metric], 0.0)
                    self.assertLessEqual(result[metric], 1.0 + 1e-12)

                self.assertGreaterEqual(
                    result["bg_goodput_mbps"], 0.0
                )

    def test_reproducibility_excluding_measured_cpu_time(self):
        config = self.config()
        scheduler = SchedulerConfig(stations=config.stations)

        a = simulate(
            make_workload(config, 9), "proposed", scheduler
        )
        b = simulate(
            make_workload(config, 9), "proposed", scheduler
        )

        a.pop("scheduler_us_per_decision")
        b.pop("scheduler_us_per_decision")

        for key in a:
            if isinstance(a[key], float) and math.isnan(a[key]):
                self.assertTrue(math.isnan(b[key]))
            else:
                self.assertEqual(a[key], b[key])

    def test_airtime_does_not_exceed_service_time(self):
        config = self.config()
        result = simulate(
            make_workload(config, 3),
            "proposed",
            SchedulerConfig(stations=config.stations),
        )

        for airtime, service in zip(
            result["per_station_airtime_s"],
            result["per_station_service_s"],
        ):
            self.assertLessEqual(airtime, service + 1e-12)

    def test_packet_log_contains_every_packet_once(self):
        config = self.config()
        workload = make_workload(config, 5)

        result = simulate(
            workload,
            "proposed",
            SchedulerConfig(stations=config.stations),
            packet_logs=True,
        )

        ids = [row["packet_id"] for row in result["packet_log"]]

        self.assertEqual(len(ids), len(workload.packets))
        self.assertEqual(len(set(ids)), len(ids))

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError):
            ModelConfig(stations=0)

        with self.assertRaises(ValueError):
            ModelConfig(bad_enter=1.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
