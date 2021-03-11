FROM ubuntu:20.04

# Allow service to handle stops gracefully
STOPSIGNAL SIGQUIT

# Set pip to have cleaner logs and no saved cache
ENV PIP_NO_CACHE_DIR=false \
    PIPENV_HIDE_EMOJIS=1 \
    PIPENV_NOSPIN=1 \
    DEBIAN_FRONTEND=noninteractive

# Update
RUN apt-get update

# Fix missing packages
RUN apt-get update --fix-missing

# Install apt-utils
RUN apt-get install -y apt-utils

# Install python
RUN apt-get install -y python3.8

RUN apt-get install -y python3-pip

# Install project dependencies
RUN pip3 install -U pipenv

# Copy the project files into working directory
COPY . .

# Install the dependencies
RUN pipenv install --system --deploy

# Install chrome
RUN apt install -y /poshmark/poshmark_client/chrome.deb

# Run web server through custom manager
ENTRYPOINT ["python3", "manage.py"]
CMD ["start"]