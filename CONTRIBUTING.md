# Contributing to Codecat

Thank you for considering contributing to Codecat! We appreciate your help in making this project better. Your contributions help us create a more robust, reliable, and feature-rich application for everyone.

## How to Contribute

There are many ways to contribute, from reporting bugs to writing code:

1.  **Reporting Issues:**

    - If you find a bug, have a suggestion, or want to request a feature, please check the [Issues Page](https://github.com/Exonymos/codecat/issues) first to see if a similar item already exists.
    - If not, please [open a new issue](https://github.com/Exonymos/codecat/issues/new/choose), providing as much detail as possible.

2.  **Pull Requests (Code Contributions):**
    - If you'd like to contribute code, please follow these steps:
      - **Fork the Repository:** Create your own copy of the Codecat repository on GitHub.
      - **Create a Branch:** Create a descriptive branch name for your feature or bug fix from the `main` branch (e.g., `git checkout -b feature/add-new-exporter` or `git checkout -b fix/scanner-bug`).
      - **Set Up Development Environment:** Follow the [Development Setup](#development-setup) section below.
      - **Make Changes:** Write your code, ensuring it adheres to the project's coding standards.
      - **Test Your Changes:** Add relevant tests for any new functionality or bug fixes. Ensure all tests pass by running `pytest`.
      - **Run Linters and Formatters:** Ensure your code is clean by running the tools described in [Quality Checks & Testing](#quality-checks--testing).
      - **Commit Changes:** Commit your work with clear and concise commit messages.
      - **Push to Your Fork:** Push your branch to your forked repository on GitHub.
      - **Open a Pull Request:** Go to the original Codecat repository and open a pull request from your branch to the `main` branch. Provide a clear description of your changes and link to any relevant issues.

## Development Setup

1.  **Prerequisites:** Ensure you have Python (3.10+) installed.
2.  **Fork and Clone:** Fork the repository and clone your fork locally.
3.  **Create and Activate a Virtual Environment:**

    ```bash
    # Windows
    python -m venv .venv
    .\.venv\Scripts\activate

    # Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

4.  **Install Dependencies:**
    Install the project in editable mode along with all development tools:
    ```bash
    pip install -e .[dev]
    ```

## Quality Checks & Testing

To maintain code quality and consistency, please run the following tools locally before submitting a pull request.

- **Formatting (Black):** `black .`
- **Linting (Flake8):** `flake8 .`
- **Type Checking (Pyright):** `pyright .`
- **Testing (Pytest):** `pytest`

## Code of Conduct

Please note that this project is released with a [Contributor Code of Conduct](./CODE_OF_CONDUCT.md). By participating in this project, you agree to abide by its terms.
