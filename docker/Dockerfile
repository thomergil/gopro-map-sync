FROM adoptopenjdk/openjdk16:latest

RUN apt-get update
RUN apt-get install -y vim python3 git cmake build-essential pipenv ffmpeg

RUN mkdir /src
WORKDIR /src

COPY docker/gopro2gpx /src/gopro2gpx
COPY docker/gpmf-parser /src/gopro2gpx/gpmf-parser
WORKDIR /src/gopro2gpx
RUN cmake .
RUN make
RUN cp gopro2gpx /usr/local/bin/

WORKDIR /src/
RUN curl -L https://github.com/zdila/gpx-animator/archive/v1.7.tar.gz | tar xfz -
WORKDIR /src/gpx-animator-1.7
RUN ./gradlew assemble

RUN mkdir /src/gopro-map-sync
WORKDIR /src/gopro-map-sync
COPY Pipfile .
RUN pipenv install
COPY __init__.py .
COPY gpxlib.py .
COPY gpxmapmovie .

# ENTRYPOINT ["/bin/bash"]
ENTRYPOINT ["/usr/bin/pipenv", "run", "/src/gopro-map-sync/gpxmapmovie", "-j", "/src/gpx-animator-1.7/build/libs/gpx-animator-1.7.0-all.jar"]
