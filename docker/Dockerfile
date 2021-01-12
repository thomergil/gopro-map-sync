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

COPY docker/gpx-animator-1.6/ /src/gpx-animator
WORKDIR /src/gpx-animator
RUN ./gradlew assemble

RUN mkdir /src/gopro-map-sync
WORKDIR /src/gopro-map-sync
COPY Pipfile-3.7 Pipfile
RUN pipenv install
COPY __init__.py .
COPY gpxlib.py .
COPY gpxanimator .

# ENTRYPOINT ["/bin/bash"]
ENTRYPOINT ["/usr/bin/pipenv", "run", "/src/gopro-map-sync/gpxanimator", "-j", "/src/gpx-animator/build/libs/gpx-animator-1.6.0-all.jar"]
