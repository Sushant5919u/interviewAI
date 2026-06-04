# InterviewAI – Multi-Agent AI Interview Preparation Platform

InterviewAI is a Python and Streamlit-based application designed to help candidates prepare for interviews through personalized practice and feedback. The platform uses a multi-agent architecture to analyze resumes, generate tailored interview questions, evaluate responses, identify weak areas, and create a structured learning roadmap for improvement.

## Overview

Traditional interview preparation is often generic and does not consider a candidate's actual experience, skills, or projects. InterviewAI addresses this problem by using resume-based analysis and performance evaluation to create a customized interview preparation experience.

## Key Features

* Resume analysis from PDF documents
* Skill extraction and classification
* ATS-style resume scoring
* Personalized technical, project-based, and behavioral questions
* Easy, Medium, and Hard interview modes
* General and company-specific interview preparation
* Answer evaluation based on accuracy, completeness, communication, and confidence
* Detailed performance reports with category-wise analysis
* Four-week personalized learning roadmap
* Interview history and progress tracking using SQLite
* Optional Gemini AI integration with local fallback support

## Project Structure

```text
interview-agent/
│
├── app.py
├── agents/
│   ├── resume_agent.py
│   ├── question_agent.py
│   ├── evaluation_agent.py
│   └── roadmap_agent.py
│
├── utils/
│   ├── pdf_reader.py
│   └── prompts.py
│
├── database/
│   └── sqlite.db
│
├── requirements.txt
└── README.md
```

## Installation

```bash
cd interview-agent
python -m pip install -r requirements.txt
streamlit run app.py
```

## Optional Gemini Configuration

The application can run completely offline without an API key. To enable Gemini-powered responses, configure the following environment variables before starting the application:

```bash
set GEMINI_API_KEY=your_api_key
set GEMINI_MODEL=gemini-2.0-flash
```

## How It Works

1. Start a new interview session.
2. Enter candidate information and upload a PDF resume.
3. Select the target company, interview difficulty, focus areas, and number of questions.
4. Complete the generated mock interview.
5. Receive answer-level feedback and performance evaluation.
6. Generate a final report highlighting strengths, weaknesses, and improvement areas.
7. Follow the personalized four-week learning roadmap.

## Multi-Agent Architecture

### Resume Agent

Extracts text from resumes, identifies skills, projects, education, and experience, and calculates an ATS-style score.

### Question Agent

Generates personalized interview questions based on the candidate's resume, selected company, difficulty level, and focus areas.

### Evaluation Agent

Analyzes candidate responses and provides feedback on technical accuracy, completeness, communication quality, and confidence.

### Roadmap Agent

Creates a customized four-week learning plan focused on improving weak areas identified during the interview.

## Database

The SQLite database (`database/sqlite.db`) stores:

* User information
* Resume analysis results
* Interview sessions
* Generated questions
* Answer evaluations
* Learning roadmaps

The required tables are automatically created and updated when the application starts.

## Objective

InterviewAI aims to make interview preparation more personalized, structured, and effective by connecting resume analysis with real-time interview evaluation. Instead of practicing generic questions, candidates receive targeted feedback and learning recommendations based on their actual skills, experience, and performance.
