# Test Case Prioritization Evaluation Toolkit

This toolkit is designed to evaluate the effectiveness of various test case prioritization strategies across different benchmarks and coverage criteria in software testing. It includes Python scripts for compiling benchmark programs, generating test suites using different coverage and prioritization strategies, and evaluating these suites' ability to expose faults. The toolkit aims to provide insights into the fault detection capabilities of each strategy, facilitating better understanding and application in real-world software testing scenarios.

## Features

- **Benchmark Compilation:** Compiles a set of predefined benchmark programs with support for coverage analysis.
- **Test Suite Generation:** Generates test suites using different coverage (Statement, Branch) and prioritization strategies (Random, Total, Additional).
- **Evaluation of Test Suites:** Evaluates the generated test suites against both original and faulty versions of the benchmark programs to measure their effectiveness in exposing faults.
- **Results Analysis:** Aggregates and saves the evaluation results for further analysis.

## Requirements

- Python 3.x
- Required Python libraries are listed in the `requirements.txt` file. To install the requirements:
```
pip install -r requirements.txt
```
- The code assumes `gcc-13` and `gcov-13` are installed in the machine.


Ensure you have the necessary Python environment and libraries installed before running the scripts.

## Usage

To utilize this toolkit effectively, follow these steps:

1. **Setup Benchmark Programs:** Ensure your benchmark programs are placed within the `benchmarks` directory.
2. **Generate Test Suites:** Execute the generation script by running `python3 script.py` or use the interactive Python notebook `script.ipynb` for an interactive exploration. This will produce test suites in the `test_suites` directory, based on the selected coverage and prioritization strategies.
```bash
python3 script.py
```
3. **Evaluate Test Suites:** The script evaluates the fault detection capability of each generated test suite against both the original and faulty versions of the benchmark programs.
4. **Analyze Results:** Find the evaluation results in the `results.csv` file, allowing for a comprehensive analysis of the test suite effectiveness.


## Generated Test Suites and Reports

### Test Suites
The generated test suites, which are the outcome of the execution process involving various prioritization strategies, are stored within the `test_suites` folder. This organization facilitates easy access and management of the test data generated for each benchmark program and strategy combination.

### Results
After evaluating the test suites, detailed reseults are generated. The result report is available in the `results.csv` file.


