# Syncing a GoPro video with a moving map

### Introduction

This is a set of tools to **exactly** synchronize GoPro footage with a moving map. The heavy lifting is performed by [GPX Animator](https://gpx-animator.app/), but it leverages other tools, such as [gopro2gpx](https://github.com/NetworkAndSoftware/gopro2gpx).

`gopro-map-sync` uses telemetry data (most critically, GPS location) that is stored as metadata in GoPro movie files. It can handle footage that was recorded in TimeWarp mode. It can optionally reference a GPX file (for example, from a Garmin or Wahoo) file to annotate the video with additional information.

##### One wrapper: `gpxanimator`

Ideally, it should all work with just one tool, `gpxanimator`. In reality, however, the GoPro metadata is sloppy, and some tweaking will be required.

##### Additional tools for manipulating GPX files

For that purpose,`gopro-map-sync` provides a number of additional tools to inspect and manipulate GPX files, if necessary. Specifically, `gpxstats ` display a GPX file in human-readable format, `gpxclean ` removes outlier points, `gpxcat` concatenates GPX files, `gpxtac` intelligently reverses a GPX file, `gpxdup` manipulates the start of a GPX file, `gpxshift` intelligently time shifts a GPX file, `gpxhead` displays the first few elemnts of a GPX file much like UNIX `head`, `gpxtail` displays the last few elements of a GPX file much like UNIX `tail`. Finally,`gpxcomment` is the most complex: it "zips" together a GoPro GPX file with a second GPX file (e.g., from a Garmin or Wahoo) and annotates the GoPro GPX with `<cmt>` blocks for later consumption by GPX Animator.

Most of these tools can be combined together with UNIX pipes. In other words, the output of each of these tools can be used as input for others.

### Zero installation with Docker

Assuming you have a GoPro video `bikeride.mp4`  in `/Users/john/Movies/`, run:

```bash
docker run --mount="type=bind,source=/Users/john/Movies/,target=/videos/" thomergil/gpxanimator --output /videos/movie.mp4 /videos/bikeride.mp4
```

The generated video will be at `/Users/john/Movies/movie.mp4`.

### Installation for Mac

```bash
# install python and pipenv
brew install python@3.9 pipenv

# install ffmpeg
brew install ffmpeg

# install gopro2gpx [https://github.com/NetworkAndSoftware/gopro2gpx]
brew install cmake
git clone git@github.com:NetworkAndSoftware/gopro2gpx.git
cd ./gopro2gpx
git clone git@github.com:gopro/gpmf-parser.git
cmake .
make
cd ..

# add gopro2gpx to PATH; or copy to your own PATH
mkdir -f ~/bin/
cp gopro2gpx ~/bin
export PATH=$PATH:/bin/

# install java
brew install adoptopenjdk15

# install GPX Animator [https://github.com/zdila/gpx-animator]
git clone git@github.com/zdila/gpx-animator
cd ./gpx-animator
./gradlew assemble

# install gopro-map-sync
git clone git@github.com/thomergil/gopro-map-sync
cd ./gopro-map-sync
# On macOs Big Sur (11.0) this prevents python package errors
export SYSTEM_VERSION_COMPAT=1
pipenv install
```

### Installation for Linux

```bash
# TODO: INSTALL adoptopenjdk
# see https://adoptopenjdk.net/installation.html#

echo 'You need to manually install adoptopenjdk; see above'

# install dependencies
sudo apt-get install -y vim python3 git cmake build-essential pipenv ffmpeg

# install gopro2gpx [https://github.com/NetworkAndSoftware/gopro2gpx]
git clone git@github.com:NetworkAndSoftware/gopro2gpx.git
cd ./gopro2gpx
git clone git@github.com:gopro/gpmf-parser.git
cmake .
make
cp gopro2gpx /usr/local/bin/

# install GPX Animator [https://github.com/zdila/gpx-animator]
cd ..
git clone git@github.com/zdila/gpx-animator
cd ./gpx-animator
./gradlew assemble

# install gopro-map-sync
git clone git@github.com/thomergil/gopro-map-sync
cd ./gopro-map-sync
pipenv install

# test that it works
pipenv run ./gpxanimator --help
```

### Basic usage

At its simplest, `gpxanimator` needs to know the location of the GPX Animator .jar file and one or more MP4 files. For example, to create one map movie from two GoPro videos, `GH0100017.MP4` and `GH0100018.MP4`:


```bash
# You need to replace the -j argument and point
# it at the correct .jar file in the GPX Animator project
pipenv run ./gpxanimator -j ~/src/gpx-animator/build/libs/gpx-animator-1.6-all.jar  --output movie.mp4 GH0100017.MP4 GH0100018.MP4
```

The output of this won't be great. The rest of this manual tries to make it better.

### `gpxanimator`'s order of operations

`gpxanimator` performs the following steps.

1. Collect all GoPro .mp4 and/or .gpx files from the command line or from the `--files`
   argument (further explained below).
1. If necessary, generate .gpx files from .mp4 files using `gopro2gpx`.
1. Apply `gpxclean` to remove erroneous outlier points.
1. Optionally post-process .gpx files using user-configurable pipes (see `--files` documentation); for example, `gpxdup` might be used here to pad the start
1. Concatenate all .gpx files together into one.
1. If `--reference` was used, run `gpxcomment` to annotate each GPX point with
   information from the reference GPX file (e.g., from a Garmin or Wahoo). This can be used by GPX Animator to generate meaningful information which is displayed in the comment block. It is **strongly recommended** to use the `--timezone` argument, when
   using `--reference`.
1. Compute the length of the video to be generated and optionally divide that
   number by the `--divide` argument if you plan to accelerate the GoPro footage.
1. Invoke GPX Animator with the generated .gpx file as `--input` argument, the
   computed duration as `--total-duration` argument, all arguments from
   `--args` (if used) and all other unparsed arguments from the `gpxanimator`
   command as command-line arguments.


###  `gpxanimator` command line options

The simplest command line invocation is:


```bash
gpxanimator -j gpxanimator.jar -o output.mp4 file1.mp4 [file2.mp4 [...]]
```

### Passing additional arguments to GPX Animator via `gpxanimator`'s command line

Any command line parameter **not** consumed by `gpxanimator` is passed to GPX Animator. In the following example, only the `-j` argument and the `.MP4` file arguments are consumed by `gpxanimator`; all other arguments are passed to the GPX Animator command line.  

```bash
pipenv run ./gpxanimator -j path/to/gpx-animator.jar \
   --tms-url-template 'http://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={zoom}' \
   --background-map-visibility 1.0 \
   --viewport-height 640 \
   --viewport-width 640 \
   --tail-duration 10000 \
   --pre-draw-track \
   --pre-draw-track-color '#808080' \
   --attribution-position hidden \
   --information-position hidden \
   --comment-position 'bottom left' \
   --output movie.mp4 \
   GH0100017.MP4 GH0100018.MP4
```

### Passing GPX Animator command line options using `--args` 

In the example above, the command line gets awkwardly long. You can put GPX Animator command line arguments in a file and pass it to `gpxanimator` with `--args`.

`args.txt`:

```bash
#
# Command line options for GPX Animator.
#
# Empty lines and lines starting with # are ignored
#
--tms-url-template 'http://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={zoom}'
--background-map-visibility 1.0
--viewport-height 640
--viewport-width 640
--tail-duration 10000
--pre-draw-track
--pre-draw-track-color '#808080'
--attribution-position hidden
--information-position hidden
--comment-position 'bottom left'
--output output.mp4
```

Then invoke `gpxanimator` with an `--args` argument:

```bash
# You need to replace the -j argument and point
# it at the .jar file in the GPX Animator project
pipenv run ./gpxanimator -j /path/to/gpx-animator.jar \
                         --args args.txt \
                         GH0100017.MP4 GH0100018.MP4
```

### Advanced usage: using  `--file` to list MP4 files

Sometimes you need to pass many .MP4 files to `gpxanimator` and it becomes
easier to create a file with filenames in it.

```
#
# contents of files.txt
#
# Empty lines and lines starting with # are ignored
#
./GH0100017.MP4
./GH0100018.MP4
```

Then invoke `gpxanimator` as follows:

```bash
# You need to replace the -j argument and point
# it at the .jar file in the GPX Animator project
pipenv run ./gpxanimator -j path/to/gpx-animator.jar \
                         --args args.txt \
                         --files files.txt
```

### Advanced usage: using  `--file` to use custom GPX files

Sometimes the output of `gopro2gpx` is not good enough and you need to manipulate it. You can tell `gpxanimator` to use a customer .GPX file. For example, if you have a file `GH0100017-custom.gpx` which you manipulated to better synchronize with `GH0100017.MP4`, you can specify it in the second column. `gpxanimator` will use that file rather than the output of `gopro2gpx`.

```
#
# contents of files.txt
#
# Empty lines and lines starting with # are ignored
#
./GH0100017.MP4 GH0100017-custom.gpx
./GH0100018.MP4
```

### Advanced usage: using  `--file` to manipulate GPX files

Sometimes the output of `gopro2gpx` requires only a fix. For example, my GoPro Hero 8 Black consistently drops the first 2 points in a GPX track when in TimeWarp Auto mode. `gpxdup` can fix that problem by duplicating the first point. Rather than manually creating a file, I can tell `gpxanimator` to run `gpxdup` on the output of `gopro2gpx`.

```
#
# contents of files.txt
#
# Empty lines and lines starting with # are ignored
#
./GH0100017.MP4 | gpxdup, duplicate=2
./GH0100018.MP4 | gpxdup, duplicate=1
```

Any of the functions in `gpxlib.py` can be invoked using this mechanism. Multiple commands can be piped. The follow example is functionally equivalent to the previous example.

```
#
# contents of files.txt
#
# Empty lines and lines starting with # are ignored
#
./GH0100017.MP4 | gpxdup, duplicate=1 | gpxdup, duplicate=1
./GH0100018.MP4 | gpxdup, duplicate=1
```

### Advanced usage: combine with a "real" GPX file

GPX data extracted from GoPro MP4 with `gopro2gpx` synchronizes well with GoPro footage, but speed and time are incorrect, especially if footage was shot in TimeWarp mode. `gpxanimator` can "reconstruct" the correct information by copying it from another GPX file with the `--reference` argument. For example:

```bash
# You need to replace the -j argument and point
# it at the .jar file in the GPX Animator project
pipenv run ./gpxanimator -j path/to/gpx-animator.jar \
                         --args args.txt \
                         --files files.txt \
                         --reference wahoo.gpx \
                         --timezone Europe/Amsterdam
```

When you use `--reference`, it is **strongly recommended**, you also use the `--timezone` argument. (Otherwise there will be a timezone lookup for each GPX point, which dramatically impacts performance.) This process of "annotating" data is messy and imperfect, especially as GoPro footage is interrupted (for example, for battery changes) and the Garmin or Wahoo pauses when standing still.

Under the hood, `gpxcomment` annotates the GPX by adding a `<cmt>` block to each GPX track point, which GPX Animator consumes using the `--comment-position` argument.

### Other projects

* [GPX Animator](https://gpx-animator.app/), an excellent tool originally written by [Martin Ždila](https://github.com/zdila), currently maintained by [Marcus Fihlon](https://github.com/McPringle).

* https://github.com/JoanMartin/trackanimation, a similar tool as GPX Animator.

* Compare GPX tracks using the Needleman-Wunsch algorithm ([explained](https://steemit.com/programming/@bitcalm/how-to-compare-gps-tracks)): https://github.com/jonblack/cmpgpx.

* https://github.com/remisalmon/gpx_interpolate, a tool that interpolates GPX points in a sparse GPX track.

* https://github.com/JuanIrache/gopro-telemetry (code that runs https://goprotelemetryextractor.com/free/), a tool similar to `gopro2gpx`, but not suitable for this project because it does not work correctly for TimeWarp'd footage.

* [GPX Editor](https://apps.apple.com/nl/app/gpx-editor/id924782627?mt=12), a tool to manipulate GPX files for Mac. I don't love it, but it does the job.

  
