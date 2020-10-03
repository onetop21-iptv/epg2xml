FROM python
LABEL maintainer="onetop21"

ENV TZ="Asia/Seoul"

COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /workspace
ADD https://raw.githubusercontent.com/onetop21-iptv/epg2xml/master/epg2xml.py .
COPY epg2xml.json .
COPY Channel.json .

VOLUME  /output
ENTRYPOINT python epg2xml.py
