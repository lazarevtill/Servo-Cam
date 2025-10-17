ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_ROOT_USER_ACTION=ignore

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3-pip \
        python3-dev \
        python3-opencv \
        libatlas-base-dev \
        libjpeg-dev \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        build-essential \
        i2c-tools \
    && pip3 install --no-cache-dir --upgrade pip \
    && rm -rf /var/lib/apt/lists/*

COPY rootfs /

RUN chmod +x /etc/services.d/servo-cam/run \
    && chmod +x /etc/cont-init.d/10-copy-integration

RUN pip3 install --no-cache-dir -r /opt/servo_cam/requirements.txt

WORKDIR /opt/servo_cam

CMD ["/init"]
