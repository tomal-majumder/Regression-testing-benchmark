# %%
import os
import glob
import json
import random
import subprocess
import re
import pickle
import pandas as pd
from tqdm import tqdm

# Dictionary mapping benchmark program names to their respective compilation commands.
BENCHMARK_PROGRAMS_TO_COMPILE_CMDS = {
    "tcas": ["gcc-13", "-Wno-return-type", "-g", "tcas.c", "-o", "tcas"],
    "totinfo": ["gcc-13", "-Wno-return-type", "-g", "totinfo.c", "-o", "totinfo", "-lm"],
    "schedule": ["gcc-13", "-Wno-return-type", "-g", "schedule.c", "-o", "schedule"],
    "schedule2": ["gcc-13", "-Wno-return-type", "-g", "schedule2.c", "-o", "schedule2"],
    "printtokens": ["gcc-13", "-Wno-return-type", "-g", "printtokens.c", "-o", "printtokens"],
    "printtokens2": ["gcc-13", "-Wno-return-type", "-g", "printtokens2.c", "-o", "printtokens2"],
    "replace": ["gcc-13", "-Wno-return-type", "-g", "replace.c", "-o", "replace", "-lm"]
}

# Flags for GCOV to enable test coverage analysis.
GCOV_FLAGS = ["-fprofile-arcs", "-ftest-coverage"]

# The directory containing benchmark programs.
BENCHMARKS_FOLDER = 'benchmarks'


def run_command(command, base_dir=None, shell=False):
    """
    Executes a command in a subprocess and captures its output.

    Parameters:
        command (list[str] or str): The command to run. If `shell` is False, this should be a list of the command and its arguments.
        base_dir (str, optional): The directory in which to execute the command. Defaults to None, meaning the current working directory.
        shell (bool, optional): Whether to execute the command through the shell. Defaults to False.

    Returns:
        str: The stdout and stderr output of the command as a text string.
    """
    result = subprocess.run(command, cwd=base_dir, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, shell=shell)
    return result.stdout


def natural_keys(text):
    """
    Analyzes a string to return a list of parts that is numbers as integers and the rest as text. 
    This is useful for natural sort order.
    
    Parameters:
        text (str): The string to split.
        
    Returns:
        list: A list of strings and integers derived from the input text.
    """
    return [int(c) if c.isdigit() else c for c in re.split('(\d+)', text)]

# %%
class CoverageCriteriaStrategy:
    """
    Base class for implementing coverage criteria strategies for test case prioritization.

    Attributes:
        benchmark_name (str): Name of the benchmark program.
        base_dir (str): Directory path of the benchmark.
        pickle_file (str): Path to the pickle file storing coverage information.
        test_input_file (str): Path to the file containing test inputs.
        coverage_flags (list): Additional flags for coverage analysis.

    Methods:
        apply_coverage: Collects and stores coverage information for all test cases.
        parse_json: Abstract method to parse coverage data from JSON. Must be implemented by subclasses.
    """

    def __init__(self, benchmark_name):
        """
        Initializes CoverageCriteriaStrategy with a benchmark name.
        """
        self.benchmark_name = benchmark_name
        self.base_dir = f'{BENCHMARKS_FOLDER}/{benchmark_name}'
        self.pickle_file = f'{self.base_dir}/{self.benchmark_name}_{self.__class__.__name__}.pickle'
        self.test_input_file = f'{self.base_dir}/universe.txt'
        self.coverage_flags = []
        

    def apply_coverage(self):
        """
        Collects coverage information for each test case, compiles the benchmark with coverage flags, and parses the coverage data.
        """
        if os.path.exists(self.pickle_file):
            with open(self.pickle_file, 'rb') as f:
                return pickle.load(f)
        coverage_info = {}
        all_tests = []
        with open(self.test_input_file) as test_input_file:
            for test_case in tqdm(test_input_file.readlines()):
                test_case = test_case.strip()
                coverage_info[test_case] = set()
                all_tests.append(test_case)
                compile_cmd_with_gcov = BENCHMARK_PROGRAMS_TO_COMPILE_CMDS[
                    self.benchmark_name][:3] + GCOV_FLAGS + BENCHMARK_PROGRAMS_TO_COMPILE_CMDS[
                    self.benchmark_name][3:]
                run_command(compile_cmd_with_gcov, self.base_dir)
                run_command(
                    f"./{self.benchmark_name} {test_case}", self.base_dir, True)
                run_command(
                    ["gcov-13", *self.coverage_flags, "-j", f"{self.benchmark_name}.c"], self.base_dir)
                run_command(
                    ["gzip", "-d", f"{self.benchmark_name}.gcov.json.gz"], self.base_dir)
                with open(f"{self.base_dir}/{self.benchmark_name}.gcov.json") as gcov_json_file:
                    gcov_json = json.load(gcov_json_file)
                    self.parse_json(gcov_json, coverage_info, test_case)
                for file in glob.glob(f"{self.base_dir}/{self.benchmark_name}.gc*"):
                    os.remove(file)
        with open(self.pickle_file, 'wb') as f:
            pickle.dump((all_tests, coverage_info), f)
        return (all_tests, coverage_info)

    def parse_json(self, json_content, coverage_info, test_case):
        """
        Parses the JSON content to extract coverage information.
        Abstract method, to be implemented by subclasses.
        """
        pass


class StatementCoverage(CoverageCriteriaStrategy):
    """
    Implements statement coverage criteria by extending CoverageCriteriaStrategy.
    """

    def __init__(self, benchmark_name):
        """
        Initializes StatementCoverage with a benchmark name.
        """
        super().__init__(benchmark_name)

    def parse_json(self, json_content, coverage_info, test_case):
        """
        Parses JSON content to extract statement coverage information.
        """
        for stmt_cov_info in json_content['files'][0]['lines']:
            if stmt_cov_info['count'] > 0:
                coverage_info[test_case].add(
                    stmt_cov_info['line_number'])


class BranchCoverage(CoverageCriteriaStrategy):
    """
    Implements branch coverage criteria by extending CoverageCriteriaStrategy.
    
    Attributes:
        coverage_flags (list): Overrides base class attribute with flags specific to branch coverage.
    """

    def __init__(self, benchmark_name):
        """
        Initializes BranchCoverage with a benchmark name and specific coverage flags.
        """
        super().__init__(benchmark_name)
        self.coverage_flags = ["-b", "-c"]

    def parse_json(self, json_content, coverage_info, test_case):
        """
        Parses JSON content to extract branch coverage information.
        """
        for branch_cov_info in json_content['files'][0]['lines']:
            line_number = branch_cov_info['line_number']
            for index, branch in enumerate(branch_cov_info['branches']):
                if branch['count'] > 0:
                    coverage_info[test_case].add(
                        f"{line_number}_{index}")

# %%
class PrioritizationMethodStrategy:
    """
    Base class for test case prioritization methods.

    Methods:
        prioritize_tests(all_tests, coverage_info): Abstract method to prioritize test cases based on coverage information.
    """

    def prioritize_tests(self, all_tests, coverage_info):
        """
        Abstract method for prioritizing test cases.

        Parameters:
            all_tests (list): A list of all test case names.
            coverage_info (dict): A dictionary mapping test case names to coverage data.

        Returns:
            list: A list of prioritized test case names.
        """
        pass


class RandomPrioritization(PrioritizationMethodStrategy):
    """
    Implements test case prioritization by randomly selecting tests until all lines are covered.
    """

    def prioritize_tests(self, all_tests, coverage_info):
        """
        Randomly prioritizes test cases, ensuring coverage of all lines.

        Parameters:
            all_tests (list): A list of all test case names.
            coverage_info (dict): A dictionary mapping test case names to coverage data.

        Returns:
            list: A list of prioritized test case names.
        """
        lines_covered_by_all_tests = set.union(*coverage_info.values())
        cumulative_coverage = set()
        truncated_test_suite = []
        while len(lines_covered_by_all_tests) != len(cumulative_coverage):
            random_test_idx = random.randint(0, len(coverage_info) - 1)
            random_test = all_tests[random_test_idx]
            if not coverage_info[random_test].issubset(cumulative_coverage):
                cumulative_coverage.update(coverage_info[random_test])
                truncated_test_suite.append(random_test)
        return truncated_test_suite


class TotalPrioritization(PrioritizationMethodStrategy):
    """
    Implements test case prioritization based on the total coverage each test provides.
    """

    def prioritize_tests(self, all_tests, coverage_info):
        """
        Prioritizes test cases based on the descending order of their coverage size.

        Parameters:
            all_tests (list): A list of all test case names.
            coverage_info (dict): A dictionary mapping test case names to coverage data.

        Returns:
            list: A list of prioritized test case names.
        """
        lines_covered_by_all_tests = set.union(*coverage_info.values())
        cumulative_coverage = set()
        truncated_test_suite = []
        sorted_tests = sorted(coverage_info.items(), key=lambda x: len(x[1]), reverse=True)
        prior_test_idx = 0
        while len(lines_covered_by_all_tests) != len(cumulative_coverage):
            test_case, this_coverage = sorted_tests[prior_test_idx]
            if not coverage_info[test_case].issubset(cumulative_coverage):
                cumulative_coverage.update(this_coverage)
                truncated_test_suite.append(test_case)
            prior_test_idx = prior_test_idx + 1
        return truncated_test_suite


class AdditionalPrioritization(PrioritizationMethodStrategy):
    """
    Implements test case prioritization based on the additional coverage each test provides over already selected tests.
    """
    
    def prioritize_tests(self, all_test, coverage_info):
        """
        Prioritizes test cases based on the additional unique coverage each provides, in descending order.

        Parameters:
            all_tests (list): A list of all test case names.
            coverage_info (dict): A dictionary mapping test case names to coverage data.

        Returns:
            list: A list of prioritized test case names.
        """
        lines_covered_by_all_tests = set.union(*coverage_info.values())
        cumulative_coverage = set()
        truncated_test_suite = []
        while len(lines_covered_by_all_tests) != len(cumulative_coverage):
            sorted_coverage_info = sorted(coverage_info.items(), key=lambda x: len(x[1]), reverse=True)
            test_case, this_coverage = sorted_coverage_info[0]
            del coverage_info[test_case]
            for test_coverage in coverage_info.values():
                test_coverage.difference_update(this_coverage)
            cumulative_coverage.update(this_coverage)
            truncated_test_suite.append(test_case)
        return truncated_test_suite

# %%
class TestSuiteGenerator:
    """
    Generates test suites for a given benchmark using specified coverage and prioritization strategies.

    Attributes:
        _benchmark_name (str): The name of the benchmark program.
        _coverage_strategy (CoverageCriteriaStrategy): An instance of a coverage strategy for the benchmark.
        _prioritization_strategy (PrioritizationMethodStrategy): An instance of a prioritization strategy.

    Methods:
        generate_test_suite: Generates and returns a prioritized test suite based on coverage and prioritization strategies.
        set_coverage_strategy(strategy): Updates the coverage strategy.
        set_prioritization_strategy(strategy): Updates the prioritization strategy.
    """

    def __init__(self, benchmark_name, coverage_strategy, prioritization_strategy):
        """
        Initializes the TestSuiteGenerator with a benchmark name, coverage strategy, and prioritization strategy.

        Parameters:
            benchmark_name (str): The name of the benchmark.
            coverage_strategy (CoverageCriteriaStrategy class): The class of the coverage strategy to be used.
            prioritization_strategy (PrioritizationMethodStrategy class): The class of the prioritization strategy to be used.
        """
        self._benchmark_name = benchmark_name
        self._coverage_strategy = coverage_strategy(benchmark_name)
        self._prioritization_strategy = prioritization_strategy()

    def generate_test_suite(self):
        """
        Applies the coverage strategy to collect coverage data and then prioritizes tests based on the chosen prioritization strategy.

        Returns:
            list: A list of test case names ordered according to the prioritization strategy.
        """
        all_tests,  coverage_info = self._coverage_strategy.apply_coverage()
        prioritized_tests = self._prioritization_strategy.prioritize_tests(
            all_tests, coverage_info)
        return prioritized_tests

    def set_coverage_strategy(self, strategy):
        """
        Sets a new coverage strategy.

        Parameters:
            strategy (CoverageCriteriaStrategy): An instance of a new coverage strategy.
        """
        self._coverage_strategy = strategy

    def set_prioritization_strategy(self, strategy):
        """
        Sets a new prioritization strategy.

        Parameters:
            strategy (PrioritizationMethodStrategy): An instance of a new prioritization strategy.
        """
        self._prioritization_strategy = strategy

# %%
class TestSuiteEvaluator:
    """
    Evaluates a test suite's effectiveness in exposing faults in a benchmark program.

    Attributes:
        benchmark_name (str): The name of the benchmark program.
        base_dir (str): The directory path where the benchmark is located.

    Methods:
        evaluate(test_suite): Evaluates the given test suite against both the original and faulty versions of the benchmark.
        compile_original_and_faulty(): Compiles both the original and all faulty versions of the benchmark.
    """

    def __init__(self, benchmark_name):
        """
        Initializes the evaluator with the benchmark name.

        Parameters:
            benchmark_name (str): The name of the benchmark program.
        """
        self.benchmark_name = benchmark_name
        self.base_dir = f'{BENCHMARKS_FOLDER}/{benchmark_name}'

    def evaluate(self, test_suite):
        """
        Runs the test suite against both the original and faulty versions, identifying which faults are exposed.

        Parameters:
            test_suite (list): A list of test case inputs to be evaluated.

        Returns:
            set: A set of identifiers for the faulty versions exposed by the test suite.
        """
        faulty_dirs = self.compile_original_and_faulty()
        exposed_faults = set()
        for test in test_suite:
            original_out = run_command(
                f"./{self.benchmark_name} {test}", self.base_dir, True)
            for faulty_dir in faulty_dirs:
                if faulty_dir in exposed_faults:
                    continue
                updated_test = re.sub(r'(<\s*)',  r'\g<1>' + r'../', test)
                faulty_out = run_command(
                    f"./{self.benchmark_name} {updated_test}", f"{self.base_dir}/{faulty_dir}", True)
                if original_out != faulty_out:
                    exposed_faults.add(faulty_dir)
        return exposed_faults

    def compile_original_and_faulty(self):
        """
        Compiles the original benchmark program and all of its faulty versions.

        Returns:
            set: A set of directory names containing compiled faulty versions.
        """
        run_command(
            BENCHMARK_PROGRAMS_TO_COMPILE_CMDS[self.benchmark_name], self.base_dir)
        faulty_folder_name_pattern = re.compile(r'^v\d+$')
        faulty_version_dirs = {item for item in os.listdir(self.base_dir) if os.path.isdir(
            os.path.join(self.base_dir, item)) and faulty_folder_name_pattern.match(item)}
        self.faulty_version_cnt = len(faulty_version_dirs)
        for faulty_version_dir in faulty_version_dirs:
            run_command(BENCHMARK_PROGRAMS_TO_COMPILE_CMDS[self.benchmark_name],
                        base_dir=f"{self.base_dir}/{faulty_version_dir}")
        return faulty_version_dirs

# %%
# Lists of benchmarks, coverage strategies, and prioritization strategies for evaluation
benchmark_names = list(BENCHMARK_PROGRAMS_TO_COMPILE_CMDS.keys())
coverage_strategies = [StatementCoverage, BranchCoverage]
prioritization_strategies = [RandomPrioritization, TotalPrioritization, AdditionalPrioritization]
results = []  # To store the results of the evaluations

# Calculate total iterations for progress tracking
total_iterations = len(benchmark_names) * len(coverage_strategies) * len(prioritization_strategies)

# Progress bar to monitor overall evaluation progress
with tqdm(total=total_iterations, desc="Overall Progress") as pbar:
    # Iterate over each combination of benchmark, coverage strategy, and prioritization strategy
    for benchmark_name in benchmark_names:
        for coverage_strategy in coverage_strategies:
            for prioritization_strategy in prioritization_strategies:
                # Generate a test suite for the current combination
                test_suite_generator = TestSuiteGenerator(benchmark_name, coverage_strategy, prioritization_strategy)
                test_suite = test_suite_generator.generate_test_suite()

                # Logging the details of the generated test suite
                print(f"Test suite for {benchmark_name}, {coverage_strategy.__name__}, {prioritization_strategy.__name__}:")
                print(len(test_suite), sorted(test_suite, key=natural_keys))

                # Save the test suite to a file
                suite_name = f"{prioritization_strategy.__name__.lower()}-{coverage_strategy.__name__.lower()}-suite.txt"
                suite_path = os.path.join("test_suites", benchmark_name, suite_name)
                os.makedirs(os.path.dirname(suite_path), exist_ok=True)
                with open(suite_path, "w") as suite_file:
                    suite_file.write("\n".join(test_suite))

                # Evaluate the effectiveness of the generated test suite
                test_suite_evaluator = TestSuiteEvaluator(benchmark_name)
                exposed_faults = test_suite_evaluator.evaluate(test_suite)

                # Logging the results of the evaluation
                print(f"Total faults for {benchmark_name}, {coverage_strategy.__name__}, {prioritization_strategy.__name__}: {test_suite_evaluator.faulty_version_cnt}")
                print(f"Exposed faults for {benchmark_name}, {coverage_strategy.__name__}, {prioritization_strategy.__name__}:")
                print(len(exposed_faults), sorted(exposed_faults, key=natural_keys))
                print("Expose fault percentage:", f"{len(exposed_faults) / test_suite_evaluator.faulty_version_cnt * 100}%")
                print()

                # Append the results to the results list for later analysis
                results.append({
                    'Benchmark': benchmark_name,
                    'Coverage Strategy': coverage_strategy.__name__,
                    'Prioritization Strategy': prioritization_strategy.__name__,
                    'Exposed Faults Count': len(exposed_faults),
                    'Expose Faults': sorted(exposed_faults, key=natural_keys),
                    'Total Faulty Versions': test_suite_evaluator.faulty_version_cnt,
                    'Percentage Exposed Faults': len(exposed_faults) / test_suite_evaluator.faulty_version_cnt * 100
                })
                
                # Update the progress bar after each iteration
                pbar.update(1)

# Create a DataFrame from the results list and save it as a CSV file
df = pd.DataFrame(results)
df.to_csv('results.csv', index=False)

# %%
# Initialize lists of benchmarks, coverage strategies, and prioritization strategies
benchmark_names = list(BENCHMARK_PROGRAMS_TO_COMPILE_CMDS.keys())
coverage_strategies = [StatementCoverage, BranchCoverage]
prioritization_strategies = [RandomPrioritization, TotalPrioritization, AdditionalPrioritization]

# Iterate over each benchmark, coverage strategy, and prioritization strategy combination
for benchmark_name in benchmark_names:
    for coverage_strategy in coverage_strategies:
        for prioritization_strategy in prioritization_strategies:
            # Construct the suite name and path based on the strategy combination
            suite_name = f"{prioritization_strategy.__name__.lower()}-{coverage_strategy.__name__.lower()}-suite.txt"
            suite_path = os.path.join("test_suites", benchmark_name, suite_name)

            # Check for the existence of the test suite file
            if not os.path.exists(suite_path):
                print(f"Test suite file does not exist for {benchmark_name}, {coverage_strategy.__name__}, {prioritization_strategy.__name__}")
            else:
                # If the file exists, load the test suite and the universe of all tests
                with open(suite_path, "r") as suite_file:
                    test_suite = suite_file.read().splitlines()
                    with open(f"{BENCHMARKS_FOLDER}/{benchmark_name}/universe.txt", "r") as universe_file:
                        universe_tests = universe_file.read().splitlines()

                        # Identify any tests in the suite that are missing from the universe
                        missing_tests = set(test_suite) - set(universe_tests)
                        if missing_tests:
                            print(f"Missing tests in universe.txt for {benchmark_name}, {coverage_strategy.__name__}, {prioritization_strategy.__name__}:")
                            print(missing_tests)



