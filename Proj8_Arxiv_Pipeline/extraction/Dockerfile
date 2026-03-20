# 1. Start with a lightweight version of Python 3.10
FROM python:3.10-slim

#2. Set the working directory in the container
WORKDIR /app

# 3. Copy the requirements file into the conatiner
COPY requirements.txt .

# 4. Tell the container to install the dependencies
RUN pip install --no-cache-dir -v -r requirements.txt

# 5. Copy our Python script into the container
COPY extract.py .

# 6. The default command to run when the container starts
CMD ["python", "extract.py"]

