# IntelliApply

An end-to-end local Python pipeline leveraging Vision LLMs and `python-docx` XML editing to dynamically tailor resumes, scrape recruiter emails, and generate personalized draft messages to recruiters.

## Table of Contents

- [About IntelliApply](#about-intelliapply)
- [Key Features & Benefits](#key-features--benefits)
- [Technologies](#technologies)
- [Prerequisites & Dependencies](#prerequisites--dependencies)
- [Installation & Setup](#installation--setup)
- [Configuration Options](#configuration-options)
- [Usage Examples](#usage-examples)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## About IntelliApply

IntelliApply is a powerful local Python-based pipeline designed to streamline and automate the tedious process of job application customization. By integrating cutting-edge Vision Large Language Models (LLMs) and precise `python-docx` XML manipulation, it intelligently adapts your resume to specific job descriptions. Beyond resume tailoring, IntelliApply takes it a step further by scraping relevant recruiter contact information and crafting personalized outreach messages, significantly boosting your application's impact and saving you valuable time.

## Key Features & Benefits

*   **Dynamic Resume Tailoring**: Leverages Vision LLMs to analyze job descriptions and your existing resume, identifying key skills and experiences to highlight.
*   **Precise `python-docx` XML Editing**: Directly manipulates the XML structure of `.docx` files, ensuring accurate and nuanced resume modifications without losing formatting.
*   **Recruiter Email Scraping**: Automates the process of finding and extracting recruiter email addresses from job postings or company career pages.
*   **Personalized Draft Message Generation**: Generates tailored cover letter snippets or direct outreach messages to recruiters, increasing engagement rates.
*   **End-to-End Local Pipeline**: All processing is done locally, providing enhanced privacy and control over your data.
*   **Increased Application Efficiency**: Significantly reduces the manual effort and time required for customizing applications.
*   **Improved Job Application Success Rates**: Custom-tailored resumes and personalized outreach make your applications stand out.

## Technologies

IntelliApply is built using the following core technologies:

*   **Python 3.x**: The primary programming language for the entire pipeline.
*   **Vision LLM Framework**: For semantic understanding of job descriptions and resume content, as well as generating tailored text. (e.g., OpenAI's GPT-4V, Google Gemini Pro Vision - specific implementation depends on chosen API).
*   [`python-docx`](https://python-docx.readthedocs.io/): A powerful library for creating, modifying, and reading Microsoft Word `.docx` files. Used here for precise XML-level editing.
*   **Web Scraping Libraries**: (e.g., `Requests`, `BeautifulSoup4`, `Selenium`) For fetching and parsing web content to extract job descriptions and recruiter contact information.
*   **Email Libraries**: For formatting and potentially sending generated email drafts.

## Prerequisites & Dependencies

Before you can run IntelliApply, ensure you have the following installed:

*   **Python 3.8+**: Download and install from [python.org](https://www.python.org/downloads/).
*   **`pip`**: Python's package installer, usually comes bundled with Python.
*   **Vision LLM API Key**: An API key from your chosen Vision LLM provider (e.g., OpenAI API Key, Google Cloud API Key for Gemini, etc.).

### Project Dependencies

All required Python libraries are listed in `requirements.txt`.

## Installation & Setup

Follow these steps to get IntelliApply up and running on your local machine:

1.  **Clone the repository**:

    ```bash
    git clone https://github.com/mark21097/IntelliApply.git
    cd IntelliApply
    ```

2.  **Create a virtual environment** (recommended):

    ```bash
    python -m venv venv
    ```

3.  **Activate the virtual environment**:

    *   **On Windows**:
        ```bash
        .\venv\Scripts\activate
        ```
    *   **On macOS/Linux**:
        ```bash
        source venv/bin/activate
        ```

4.  **Install project dependencies**:

    ```bash
    pip install -r requirements.txt
    ```
    *(Note: A `requirements.txt` file will be generated based on the inferred dependencies in a future commit.)*

5.  **Set up API Keys**:
    Create a `.env` file in the root directory of the project and add your Vision LLM API key. Replace `YOUR_API_KEY_HERE` with your actual key.

    ```
    # .env
    VISION_LLM_API_KEY=YOUR_API_KEY_HERE
    ```
    *(The specific environment variable name might vary based on the LLM provider chosen for integration, e.g., `OPENAI_API_KEY`.)*

## Configuration Options

IntelliApply offers several configurable options to fine-tune its behavior. These can typically be set via command-line arguments, a `config.ini` file, or environment variables.

*   **`VISION_LLM_API_KEY`**: (Environment Variable) Your API key for the Vision LLM service.
*   **`INPUT_RESUME_PATH`**: (Configuration/CLI Argument) Path to your original resume `.docx` file.
*   **`JOB_DESCRIPTION_URL`** / **`JOB_DESCRIPTION_TEXT`**: (Configuration/CLI Argument) The URL to the job posting or the raw text of the job description.
*   **`OUTPUT_RESUME_PATH`**: (Configuration/CLI Argument) Path where the tailored resume `.docx` will be saved.
*   **`OUTPUT_MESSAGE_PATH`**: (Configuration/CLI Argument) Path where the generated draft message will be saved.
*   **`LLM_MODEL_NAME`**: (Configuration/CLI Argument) Specify the exact LLM model to use (e.g., `gpt-4-vision-preview`, `gemini-pro-vision`).
*   **`SCRAPING_DOMAINS`**: (Configuration/List) A list of domains to prioritize or restrict email scraping from.
*   **`TEMPERATURE`**: (Configuration/CLI Argument) Controls the creativity of the LLM responses (0.0 for deterministic, 1.0 for highly creative).

## Usage Examples

Once installed and configured, you can run IntelliApply from your terminal.

The general workflow involves providing a job description (URL or text) and your base resume.

### Example: Tailor Resume and Generate Message from Job URL

```bash
python main.py \
    --job-url "https://example.com/job-posting-url" \
    --resume "path/to/your/original_resume.docx" \
    --output-resume "path/to/save/tailored_resume.docx" \
    --output-message "path/to/save/recruiter_message.txt"
```

### Example: Tailor Resume and Generate Message from Text File

If the job description is in a local text file:

```bash
python main.py \
    --job-text-file "path/to/job_description.txt" \
    --resume "path/to/your/original_resume.docx" \
    --output-resume "path/to/save/tailored_resume.docx" \
    --output-message "path/to/save/recruiter_message.txt"
```

The script will:
1.  Parse the job description.
2.  Analyze your resume and the job description using the Vision LLM.
3.  Generate a tailored `.docx` resume.
4.  Attempt to scrape recruiter email(s).
5.  Generate a personalized draft message.
6.  Save the outputs to the specified paths.

## Contributing

We welcome contributions to IntelliApply! If you have suggestions for improvements, new features, or bug fixes, please follow these steps:

1.  **Fork the repository**.
2.  **Create a new branch** for your feature or bug fix: `git checkout -b feature/your-feature-name` or `fix/bug-description`.
3.  **Make your changes**.
4.  **Commit your changes** with a clear and concise message: `git commit -m "feat: Add new feature for X"` or `fix: Resolve Y bug`.
5.  **Push your branch** to your forked repository: `git push origin feature/your-feature-name`.
6.  **Open a Pull Request** against the `main` branch of the original IntelliApply repository.

Please ensure your code adheres to existing style guidelines and includes relevant tests if applicable.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

*   Special thanks to the developers of Python, `python-docx`, and the various Vision LLM frameworks that make this project possible.
*   (Add any other specific libraries, tools, or individuals if relevant in the future.)
