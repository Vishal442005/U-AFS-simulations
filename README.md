U-AFS: An Urgency-Aware Fair Scheduler for Mixed Real-Time and Background Traffic in Single-AP Wi-Fi Networks
This repository contains the simulation code, datasets, and analysis scripts required to reproduce the results presented in the paper "U-AFS: An Urgency-Aware Fair Scheduler for Mixed Real-Time and Background Traffic in Single-AP Wi-Fi Networks".
Overview
U-AFS is a scheduling algorithm designed to balance the strict latency requirements of real-time traffic with the throughput needs of background traffic in a single Access Point (AP) Wi-Fi environment. This repository includes the network simulation environment, the implementation of the U-AFS scheduler, SPSA auto-tuning scripts for hyperparameter optimization, and the resulting datasets (JSON/CSV) used for our performance evaluation.
Repository Structure
 * /simulation_code: Contains the core simulation setup (e.g., ns-3 scripts) used to model the Single-AP Wi-Fi network and traffic flows.
 * /scripts: Python scripts used for SPSA auto-tuning, data parsing, and generating the final evaluation metrics.
 * /data: Contains the raw and processed simulation results in .csv and .json formats.
 * /plots: The generated graphs and visual results used in the manuscript.
Prerequisites
To run the simulations and analysis scripts locally, ensure your environment (such as Ubuntu via WSL2 or a native Linux distribution) has the following installed:
 * Python 3.8+
 * Required Python libraries (can be installed via pip install -r requirements.txt): pandas, matplotlib, numpy, json
 * Network Simulator (e.g., ns-3) configured and built in your system.
How to Run the Simulations
 * Clone the repository:
   git clone https://github.com/Vishal442005/U-AFS-Scheduler.git
cd U-AFS-Scheduler

 * Execute the simulation:
   Navigate to the simulation directory and run the main script. (Update this command based on your specific execution file):
   ./run_simulation.sh

 * Run SPSA Auto-Tuning (Optional):
   To reproduce the hyperparameter tuning phase, execute:
   python scripts/spsa_tuning.py

Reproducing the Plots
If you only wish to view how the data was analyzed without re-running the entire simulation, you can use the provided CSV and JSON files.
 * Navigate to the scripts directory.
 * to get plots, csv, json files check **extra_results.zip**
License
This project is licensed under the MIT License - see the LICENSE file for details.
