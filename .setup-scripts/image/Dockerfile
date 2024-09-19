FROM artifactory.tooling.stackstate.io/docker-virtual/python:3.11.8-bullseye
RUN apt-get update && \
    apt-get install -y virtualenv apt-transport-https ca-certificates curl gnupg2 software-properties-common && \
    apt-get clean && \
    pip3 install -U pip setuptools codecov wheel

RUN curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
RUN add-apt-repository -y "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable" && \
    apt-get update && \
    apt-get install -y docker-ce docker-ce-cli containerd.io && \
    apt-get clean

RUN curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
RUN chmod +x /usr/local/bin/docker-compose
