# 🐾 Codecat

<div align="center">

**The ultimate code aggregator for LLMs, code reviews, and project archiving**

_Transform your entire codebase into a single, beautifully formatted Markdown document_

[![CI/CD Status](https://github.com/Exonymos/codecat/actions/workflows/ci.yml/badge.svg)](https://github.com/Exonymos/codecat/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/Exonymos/codecat?display_name=tag&logo=github&color=brightgreen)](https://github.com/Exonymos/codecat/releases/latest)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-yellow.svg)](https://opensource.org/license/gpl-3-0)
[![Downloads](https://img.shields.io/github/downloads/Exonymos/codecat/total?color=blue&logo=github)](https://github.com/Exonymos/codecat/releases)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

[**🚀 Quick Start**](#-quick-start) • [**📖 Usage**](#-usage) • [**💡 Examples**](#-examples) • [**🛠️ Development**](#%EF%B8%8F-development)

</div>

---

## 🌟 What is Codecat?

Codecat is a lightning-fast, Python-powered CLI tool that **aggregates your entire project into a single, perfectly formatted Markdown file**. Built with [Typer](https://github.com/fastapi/typer) and [Rich](https://github.com/Textualize/rich), it features multi-threaded processing and an elegant terminal interface.

**Perfect for:**

- 🤖 **AI Development** - Feed complete project context to LLMs like GPT-4, Claude, or Copilot
- 👥 **Code Reviews** - Share comprehensive project snapshots with your team
- 📚 **Documentation** - Create portable archives of your codebase
- 🔍 **Analysis** - Get insights into your project structure and statistics

## ✨ Key Features

### 🚀 **Performance First**

- **Multi-threaded scanning** processes files in parallel
- **Smart binary detection** skips non-text files automatically
- **Optimized for large codebases** with thousands of files

### 🎨 **Beautiful Interface**

- **Rich CLI** with progress bars and color-coded output
- **Real-time statistics** showing files processed and lines counted
- **Intuitive commands** that just work out of the box

### 🧠 **Intelligent Processing**

- **Automatic language detection** for proper syntax highlighting
- **Dynamic fence handling** for code blocks containing backticks
- **Glob pattern support** for flexible file inclusion/exclusion

### ⚙️ **Highly Configurable**

- **JSON configuration** with sensible defaults
- **Command-line overrides** for any setting
- **Project-specific rules** via `.codecat_config.json`

## 🚀 Quick Start

### Installation

Choose your preferred installation method:

<details>
<summary><b>📦 Pre-built Executables (Recommended)</b></summary>

Download the latest executable for your platform from our [**Releases Page**](https://github.com/Exonymos/codecat/releases/latest):

#### Windows

```cmd
# Download codecat-windows.exe and rename to codecat.exe
# Add to PATH for global access
codecat --help
```

#### Linux

```bash
# Download codecat-linux
chmod +x codecat-linux
sudo mv codecat-linux /usr/local/bin/codecat
codecat --help
```

</details>

<details>
<summary><b>🐍 Install from Source</b></summary>

```bash
# Clone the repository
git clone https://github.com/Exonymos/codecat.git
cd codecat

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # On Linux: source .venv/bin/activate

# Install in development mode
pip install -e .
```

</details>

### First Run

```bash
# Generate a config file (optional but recommended)
codecat generate-config

# Scan your current project
codecat run .

# View project statistics without creating output
codecat stats .
```

## 📖 Usage

### Core Commands

| Command                   | Description                               | Example                    |
| ------------------------- | ----------------------------------------- | -------------------------- |
| `codecat run <path>`      | Scan directory and create Markdown output | `codecat run ./my-project` |
| `codecat stats <path>`    | Show project statistics without output    | `codecat stats .`          |
| `codecat generate-config` | Create configuration template             | `codecat generate-config`  |

### Command-Line Options

```bash
# Example: run with several common options
codecat run .
  --output-file "project-snapshot.md"
  --include "*.py"
  --include "*.md"
  --exclude "tests/*"
  --verbose
  --dry-run
```

| Option          | Description                   | Default             |
| --------------- | ----------------------------- | ------------------- |
| `--output-file` | Output filename               | `codecat_output.md` |
| `--include`     | File patterns to include      | `*`                 |
| `--exclude`     | File patterns to exclude      | See config          |
| `--verbose`     | Detailed output               | `False`             |
| `--dry-run`     | Preview without creating file | `False`             |

## 💡 Examples

### Basic Usage

```bash
# Simple scan of current directory
codecat run .

# Scan specific directory with custom output
codecat run ./my-project --output-file "project-complete.md"

# Get project insights without generating output
codecat stats ./large-codebase
```

### Advanced Filtering

Use flags multiple times for multiple patterns.

```bash
# Include only Python, TypeScript, and JavaScript files
codecat run . --include "*.py" --include "*.js" --include "*.ts" --output-file "backend-code.md"

# Exclude test directories, config files, and node_modules
codecat run . --exclude "test*" --exclude "*config*" --exclude "node_modules"
```

### Configuration-Based Workflow

```bash
# 1. Generate config template
codecat generate-config

# 2. Edit .codecat_config.json to your needs
# 3. Run with your custom configuration
codecat run .
```

## 🛠️ Development

### Setting Up Development Environment

```bash
# Fork and clone
git clone https://github.com/YOUR-USERNAME/codecat.git
cd codecat

# Setup virtual environment
python -m venv .venv
.venv\Scripts\activate  # On Linux: source .venv/bin/activate

# Install with development dependencies
pip install -e .[dev]
```

### Development Workflow

```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
pyright .

# Run tests with coverage
pytest --cov=src/codecat --cov-report=html

# Run specific test
pytest tests/test_config.py -v
```

### Building Executables

```bash
# Windows
python generate_version_file.py
pyinstaller codecat.spec

# Linux
pyinstaller --noconfirm --onefile --console --name codecat src/codecat/__main__.py
```

### Contributing Guidelines

We welcome contributions! Please:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Follow** our coding standards (Black formatting, type hints)
4. **Add tests** for new functionality
5. **Update documentation** if needed
6. **Submit** a pull request

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines.

## 🤔 FAQ

<details>
<summary><b>Why use Codecat instead of manual copy-paste?</b></summary>

Codecat automatically handles:

- File discovery and filtering
- Binary file detection
- Proper Markdown formatting
- Code block escaping
- Project statistics
- Large codebase processing

Manual approaches are error-prone and time-consuming for anything beyond trivial projects.

</details>

<details>
<summary><b>How does Codecat handle large projects?</b></summary>

Codecat uses multi-threading to process files in parallel and includes safeguards:

- Configurable file size limits
- Binary file detection and skipping
- Memory-efficient streaming for large files
- Progress indication for long-running operations
</details>

<details>
<summary><b>What file types does Codecat support?</b></summary>

Codecat processes any text-based file and automatically detects:

- Programming languages (Python, JavaScript, Java, C++, etc.)
- Markup languages (HTML, XML, Markdown)
- Configuration files (JSON, YAML, TOML, INI)
- Documentation files (TXT, RST, etc.)

Binary files are automatically skipped to prevent corruption.

</details>

## 📄 License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](./LICENSE) file for details.

## 🙋‍♂️ Support

- **🐛 Bug Reports**: [Open an issue](https://github.com/Exonymos/codecat/issues/new?template=bug_report.md)
- **💡 Feature Requests**: [Request a feature](https://github.com/Exonymos/codecat/issues/new?template=feature_request.md)

---

<div align="center">

**⭐ If Codecat helps you, please consider giving it a star on GitHub! ⭐**

_Made with ❤️ by developers, for developers_

</div>
