# RESTful API Application with ami build A06

This project implements a Health Check RESTful API that monitors the health of a running service instance and checks its connectivity to a PostgreSQL database. The API provides an endpoint to verify the service's status and prevent routing traffic to unhealthy instances.

## Prerequisites

Before building and deploying this application locally, ensure you have the following prerequisites:

1. **Python 3.7 or higher**: Download and install Python from [python.org](https://www.python.org/downloads/).

2. **PostgreSQL**: Install PostgreSQL on your machine. You can download it from [postgresql.org](https://www.postgresql.org/download/).

3. **Python Virtual Environment**: It is recommended to use a virtual environment to manage your project dependencies. You can create a virtual environment using `venv` or `virtualenv`.

   ```bash
   # Create a virtual environment
   python -m venv venv

   # Activate the virtual environment
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
4. **Dependencies**: Install the required Python packages using pip. This project uses FastAPI, SQLAlchemy, and asyncpg.

    ```bash
    pip install fastapi[all] sqlalchemy asyncpg python-dotenv
5. **PostgreSQL Database**: Ensure you have a PostgreSQL database set up for the application. You can create a database using the following command in the PostgreSQL shell:

    ```sql
    CREATE DATABASE healthcheckdb;
## Build and Deploy Instructions

Follow these steps to build and deploy the application locally:

1. **Fork the Repository**: Go to the following link to fork the repository into your own GitHub account:

    Fork the Repository: https://github.com/CSYE6225Fall24AtharvaAW/webapp
2. **Clone Your Fork**: After forking the repository, clone it to your local machine using:

    ```bash
    git clone https://github.com/your-username/webapp.git
    cd webapp
Replace your-username with your GitHub username.

3. **Set Up Environment Variables**: Create a .env file in the root directory of your project and add your PostgreSQL connection string:

    ```plaintext
    DATABASE_URL=postgresql+asyncpg://username:password@localhost/healthcheckdb
Replace username, password, and healthcheckdb with your actual PostgreSQL username, password, and database name.

4. **Run the Application**: Start the FastAPI application using Uvicorn. You can run the server with:

    ```bash
    uvicorn app.main:app --reload
The application will be available at http://127.0.0.1:8000.

5. **Test the Health Check Endpoint**: You can test the /healthz endpoint by sending a GET request:

    ```bash
    curl -X GET http://localhost:8000/healthz
You should receive a response indicating the health status of the application.

6. **Access the Interactive API Documentation - (Swagger)** : FastAPI automatically generates interactive API documentation. You can access it at http://127.0.0.1:8000/docs.
