FROM adoptopenjdk/openjdk15:debian

RUN apt-get update
RUN apt-get install -y vim python3 git cmake build-essential pipenv ffmpeg

RUN mkdir /src
WORKDIR /src

COPY docker/gopro2gpx /src/gopro2gpx
WORKDIR /src/gopro2gpx
RUN cmake .
RUN make
RUN cp gopro2gpx /usr/local/bin/

WORKDIR /src/
RUN curl -L https://github.com/zdila/gpx-animator/archive/v1.6.tar.gz | tar xfz -
WORKDIR /src/gpx-animator-1.6
RUN ./gradlew assemble

RUN mkdir /src/gopro-map-sync
WORKDIR /src/gopro-map-sync
COPY Pipfile .
RUN pipenv install
COPY __init__.py .
COPY gpxlib.py .
COPY gpxanimator .

# ENTRYPOINT ["/bin/bash"]
ENTRYPOINT ["/usr/bin/pipenv", "run", "/src/gopro-map-sync/gpxanimator", "-j", "/src/gpx-animator-1.6/build/libs/gpx-animator-1.6.0-all.jar"]
