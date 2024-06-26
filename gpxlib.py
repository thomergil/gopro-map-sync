#!/usr/bin/env python

import copy
import logging
import math
import sys
from datetime import datetime, timedelta

import dateparser
import geopy.distance
import gpxpy
from dateutil import tz
from timezonefinder import TimezoneFinder


def create(gpx=None):
    """Creates a new GPX track

    Parameters:
        gpx (gpxpy.gpx.GPX): optional gpxpy.gpx.GPX object or None

    Returns:
        [gpxpy.gpx.GPX, gpx.gpx.GPXTrackSegment] tuple

        Note that if the gpx parameter is specified, the gpx.nsmap object is
        copied to the returned gpx object.
    """
    gpx_out = gpxpy.gpx.GPX()
    gpx_out.nsmap = {}
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_out.tracks.append(gpx_track)
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    if gpx and gpx.nsmap:
        gpx_out.nsmap = {**(gpx_out.nsmap), **(gpx.nsmap)}

    return gpx_out, gpx_segment


#
# Reads a file from a file or stdin.
# Returns: (GPX object, points) tuple
#
def read(fname=None):
    """Reads GPX data from a file or stdin

    Parameters:
        fname (string): file name or None

    Returns:
        [gpxpy.gpx.GPX, points] tuple
    """
    if fname:
        with open(fname, "r") as f:
            gpx = gpxpy.parse(f)
    else:
        gpx = gpxpy.parse(sys.stdin)

    return gpx, all_points(gpx)


def all_points(gpx):
    """Returns all GPX points

    Parameters:
        gpx
    """
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append(point)
    return points


# returns distance between two points
def dist(p1, p2):
    return abs(
        geopy.distance.distance(
            (p1.latitude, p1.longitude), (p2.latitude, p2.longitude)
        ).km
    )


# returns time difference between two points
def diff(p1, p2):
    return (p2.time - p1.time).total_seconds()


# --------------------------------------------------------------------------------
#
# gpxdup
#
# --------------------------------------------------------------------------------
DEFAULT_DUPLICATE = 1
DEFAULT_INDEX = 0
DEFAULT_SHIFT = 35
DEFAULT_TIME = 400  # milliseconds
DEFAULT_STRIP = 0
DEFAULT_SMART_STRIP_RADIUS = 250  # meters
DEFAULT_SMART_STRIP_LIMIT = 100


#
# Duplicates the first {duplicate} GPX points in points.
# Returns: an array of GPX points
#
def gpxdup(
    points,
    strip=DEFAULT_STRIP,
    duplicate=DEFAULT_DUPLICATE,
    time=DEFAULT_TIME,
    shift=DEFAULT_SHIFT,
    smart_strip=None,
    smart_strip_radius=DEFAULT_SMART_STRIP_RADIUS,
    smart_strip_limit=DEFAULT_SMART_STRIP_LIMIT,
    smart_duplicate=False,
):
    xpoints = []
    smart_strip_count = 0
    if smart_strip:
        _, ref_points = read(smart_strip)

        while dist(points[0], ref_points[0]) > (smart_strip_radius / 1000):
            logging.info("Pop, because dist = %f" % (dist(points[0], ref_points[0])))
            points.pop(0)
            smart_strip_count += 1

            if smart_strip_count >= smart_strip_limit:
                raise Exception(
                    "Error: unable to find point within %fkm of reference starting point within %d tries"
                    % (strip, smart_strip_limit)
                )

            if not points:
                raise Exception(
                    "Error: unable to find point within %fkm before emptying the whole track"
                    % (strip)
                )

    # pop first N points out of the list
    for _ in range(strip):
        points.pop(0)

    ndups = smart_strip_count if smart_duplicate else duplicate

    # duplicate the first point N times, line them up left to right ending up
    # in the original first point
    for idx in range(ndups + 1):
        p = copy.deepcopy(points[0])
        p.time -= (ndups - idx) * timedelta(microseconds=time * 1000)
        p.longitude -= (ndups - idx) * (shift / 100000)
        xpoints.append(p)

    # copy the rest of the track to the output
    xpoints += points[1:]
    return xpoints


# --------------------------------------------------------------------------------
#
# gpxclean
#
# --------------------------------------------------------------------------------
DEFAULT_MAXDIST = 500  # meters
DEFAULT_TOLERANCE = 1


#
# Removes points that are clearly erroneous.
# Input: GPX points
# Returns: GPX points with outlier removes
#
# Specifically, gpxclean removes a maximum of of {tolerance} points that are
# {maxdist} meters or more away from its previous point.
#
# Notice that gpxclean will not do the right thing if the first point is the
# outlier.
#
def gpxclean(points, maxdist=DEFAULT_MAXDIST, tolerance=DEFAULT_TOLERANCE):
    xpoints = []
    last_good_point, nkilled = None, 0
    for idx, point in enumerate(points):
        if idx:
            xdist = dist(last_good_point, points[idx])
            if xdist > (maxdist / 1000):
                nkilled += 1

                if nkilled > tolerance:
                    raise Exception("Too many outlier points.")
                continue

            nkilled = 0

        xpoints.append(point)
        last_good_point = point

    return xpoints


# --------------------------------------------------------------------------------
#
# gpxfill
#
# --------------------------------------------------------------------------------
#
# Interpolates points between large distances
# Input: GPX points
# Returns: GPX points with jumps interpolated
#
#
DEFAULT_FILLDIST = 25  # meters


def gpxfill(points, maxdist=DEFAULT_MAXDIST, filldist=None):
    xpoints = []
    dist_sum, count, last_good_point = 0, 0, None
    for idx, point in enumerate(points):
        if idx:
            xdist = dist(last_good_point, points[idx])
            if xdist > (maxdist / 1000):
                # diff between far-away points
                lat_diff = points[idx].latitude - last_good_point.latitude
                lng_diff = points[idx].longitude - last_good_point.longitude
                time_diff = (points[idx].time - last_good_point.time).total_seconds()

                # we're either filling the gap with points {filldist} meters
                # spaced apart, or we do it based on the average we've seen so
                # far
                avg_dist = None
                if filldist:
                    avg_dist = filldist / 1000

                elif count:
                    # determine how many points we need to fill up the gap
                    avg_dist = dist_sum / count

                npoints = math.floor(xdist / avg_dist)

                # fill in the missing points
                if avg_dist:
                    for fill_idx in range(npoints):
                        dup_point = copy.deepcopy(last_good_point)
                        dup_point.latitude = last_good_point.latitude + (
                            (fill_idx + 1) * (lat_diff / npoints)
                        )
                        dup_point.longitude = last_good_point.longitude + (
                            (fill_idx + 1) * (lng_diff / npoints)
                        )
                        dup_point.time = last_good_point.time + timedelta(
                            0, ((fill_idx + 1) * (time_diff / npoints))
                        )
                        xpoints.append(dup_point)

            dist_sum += xdist
            count += 1

        xpoints.append(point)
        last_good_point = point

    return xpoints


# --------------------------------------------------------------------------------
#
# gpxcat
#
# --------------------------------------------------------------------------------
DEFAULT_CAT_STRETCH = 1
DEFAULT_CAT_KILLGAP = False
DEFAULT_CAT_GAPLENGTH = 0


def gpxcat(
    points_list,
    stretch=DEFAULT_CAT_STRETCH,
    killgap=DEFAULT_CAT_KILLGAP,
    gaplength=DEFAULT_CAT_GAPLENGTH,
):
    """Intelligently flattens an array of an array (consisting of GPX points)"""
    xpoints, prev_point, average_gap = [], None, None
    for idx, points in enumerate(points_list):
        for point_idx, point in enumerate(points):
            # - track_start: the first time stamp in a GPX file
            # - virtual_track_start: track_start, but time-expanded as
            #   per the rules set by stretch, killgap, and
            #   gaplength
            if point_idx == 0:
                virtual_track_start = track_start = point.time

                # on 2nd and followup GPX files, optionally kill the interfile time gap
                # the virtual_track_start is the last timestamp of the previous file plus
                # the average inter-point gap (plus, optionally, an extra gaplength).
                if idx >= 1 and killgap:
                    virtual_track_start = (
                        prev_point.time
                        + timedelta(0, average_gap)
                        + timedelta(0, gaplength)
                    )

                if prev_point:
                    logging.debug("prev_point.time = %s" % (str(prev_point.time)))
                logging.debug("track_start = %s" % (str(track_start)))
                logging.debug("average_gap = %s" % (str(average_gap)))
                logging.debug("virtual_track_start = %s" % (str(virtual_track_start)))

                # new file, reset average gap tracking
                aggr_track_gaps = 0.0

            # time stretching causes every time unit to be multiplied by stretch
            point.time = virtual_track_start + timedelta(
                0, (point.time - track_start).total_seconds() * stretch
            )

            # track total amount of gaps between points for the purpose
            # of computing the average gap size
            if point_idx >= 1:
                time_diff = (point.time - prev_point.time).total_seconds()

                # uuh, time is going backwards!
                if time_diff < 0:
                    logging.debug(
                        "WARNING: time %s went backwards by %s"
                        % (str(point.time), str(time_diff))
                    )

                    # fix it by just taking the previous point and adding the average gap
                    point.time = prev_point.time + timedelta(0, average_gap)
                    logging.debug("FIX: corrected time to %s" % (str(point.time)))
                else:
                    aggr_track_gaps += time_diff

            logging.debug("time: %s" % (str(point.time)))

            # add to concatenated track
            xpoints.append(point)

            # recall last point for next iteration
            prev_point = point

            # running average of gap so far
            if point_idx >= 1:
                average_gap = aggr_track_gaps / point_idx

    return xpoints


# --------------------------------------------------------------------------------
#
# gpxshift
#
# --------------------------------------------------------------------------------
def gpxshift(points, value=None, last=False):
    # relative shift
    if value.startswith("+") or value.startswith("-"):
        shift = datetime.timedelta(microseconds=int(value) * 1000)

    # absolute shift
    else:
        time = dateparser.parse(value)
        utc_time = time.replace(tzinfo=tz.tzutc())
        idx = -1 if last else 0
        shift = utc_time - points[idx].time

    xpoints = []
    for idx, p in enumerate(points):
        p.time = p.time + shift
        xpoints.append(p)

    return xpoints


# --------------------------------------------------------------------------------
#
# gpxtac
#
# --------------------------------------------------------------------------------
def gpxtac(points, time=False):
    xpoints = []
    for idx, p in enumerate(reversed(points)):
        px = copy.deepcopy(p)
        xpoints.append(px)
        if time:
            xpoints[-1].time = points[idx].time
    return xpoints


# --------------------------------------------------------------------------------
#
# gpxcomment and utilities
#
# --------------------------------------------------------------------------------
PAUSE_THRESHOLD = 20  # seconds
DEFAULT_PAUSE_SNAP = 100  # meters


def find_pauses(ref_points, pause_snap=DEFAULT_PAUSE_SNAP):
    """Returns an array with the start indices of pauses.

    Parameters:
        ref_points (gpxpy.gpx.GPXTrackPoint[]):

    Returns:
        Array of indices into ref_points, such that the corresponding GPX point
        is the last recorded point before a pause. A time span is considered a
        pause if it exceeds PAUSE_THRESHOLD seconds.
    """
    pauses = []
    prev_point = ref_points[0]
    for idx, point in enumerate(ref_points):
        xdiff = diff(prev_point, point)
        if xdiff > PAUSE_THRESHOLD:
            logging.debug(
                "There is a %f second pause at ref[%d] between %s and %s"
                % (xdiff, idx - 1, str(prev_point.time), str(point.time))
            )
            pauses.append(idx - 1)
        prev_point = point
    return pauses


def snap_to_pause(pauses, ref_points, idx, pause_snap=DEFAULT_PAUSE_SNAP):
    """
    Returns the index of a pause start if the given point is close enough.

    Parameters:
        pauses (int[]): an array of indices into ref_points[], pointing at the last point before a pause,
                        as created by find_pauses()
        ref_points (gpxpy.gpx.GPXTrackPoint[]): an array of GPX points
        idx (int): an index in ref_points[]

    Returns:
        If any entry p in pause[] for which distance(ref_points[idx],
        ref_points[p]) < pause_snap, it returns p. Otherwise it returns idx.
    """

    # try to round stopping point to pause in ref
    mindiff, minidx = None, None
    for p in pauses:
        d = abs(idx - p)
        if mindiff is None or d < mindiff:
            mindiff = d
            minidx = p

    # this is too far from the pause to make sense
    pause_dist = dist(ref_points[idx], ref_points[minidx])

    if pause_dist > (pause_snap / 1000):
        logging.debug("pause_dist of %f is too far to make sense", pause_dist)
        minidx = idx

    return minidx


def create_modified_point(point, time, to_zone_str, speed_in_ms, cumulative_dist):
    """Creates a new GPX point with an informative <cmt> block

    Parameters:
        point (gpxpy.gpx.GPXTrackPoint[]): a pre-existing GPX point
        time (datetime): time of new GPX point
        to_zone_str (string): the time zone of the new GPX point, based on lat,lng, or None to force a lookup
        speed_in_ms (float): speed in m/s
        cumulative_dist (float): the cumulative distance so far

    Returns:
        A GPX point with a <cmt> block
    """
    # convert speed from m/s to km/h
    speed_in_kmh = speed_in_ms * 3.6

    # force a timezone lookup for this point
    if not to_zone_str:
        tf = TimezoneFinder()
        to_zone_str = tf.timezone_at(lng=point.longitude, lat=point.latitude)

    # convert point time to timezone
    to_zone = tz.gettz(to_zone_str)
    utc_time = time.replace(tzinfo=tz.tzutc())
    time = utc_time.astimezone(to_zone)

    # construct <cmt> block for <trkpt>
    point.comment = "%s\n%s\n%5.2f km\n%d km/h" % (
        time.strftime("%b %-d, %Y"),
        time.strftime("%H:%M:%S"),
        cumulative_dist,
        speed_in_kmh,
    )
    logging.debug("segment_points.append(%s)" % (str(point)))
    logging.debug("comment:\n%s" % (str(point.comment)))

    return point


DEFAULT_RADIUS = 0.1  # km
RADIUS_MIN = 0.10  # anything within this # of km is considered within RADIUS
RADIUS_TOLERANCE = 2.50  # anything outside of 20 meters is subject to RADIUS_TOLERANCE


def find_closest(p, refs, start, radius=DEFAULT_RADIUS, search="best_in_radius"):
    """
    Finds the geographically closest GPX point in a track given another GPX point.

    Parameters:
        p (gpxpy.gpx.GPXTrackPoint): the point to look for
        refs (gpxpy.gpx.GPXTrackPoint[]): an array of GPX points in which to look for the point closest to p
        start (int): offset in refs where to start looking
        radius (float): a radius around p that affects the search
        search (string): 'first_in_radius' or 'last_in_radius' or 'best_in_radius'

    Returns:
        An integer denoting the index in refs[] which is the point that matches the search criteria.

    The simplest (and slowest) version of finding the point closest to p is
    computing the difference between p and each point in refs[] and returning
    the index in refs[] that corresponds with the smallest distance. While
    correct, that is also slow.

    The start parameter indicates where in refs[] to start looking. Presumably
    if a previous iteration was to find a point right before p, then it is safe
    to assume that the closest point to p is close to the previous result.

    To prevent find_closest having to inspect refs[start,-1], the 'search'
    parameter further bounds how far it will search away from what is likely
    the best result.

    Consider the following situation:

                  [          ]
                [             ]
    p1  p2  p3 [ p4 p5 p6 p7 p8 ] p9 ...
                [             ]
                  [          ]

    The square brackets delineate the diameter around the correct answer. Half
    that distance is the radius.

    Assuming that the caller is happy enough to accept the belief that once the
    search is outside of a certain radius of p, we won't come back to find an
    even better point. (Note that this assumption can break down for a track
    that crosses the same geographic point multiple times.)

    search == 'first_in_radius' will return p4, search == 'last_in_radius' will
    return p8. search == 'best_in_radius' will return p6.

    Note that anything within RADIUS_MIN will be considered within radius, even
    if the 'radius' parameter is smaller. Otherwise, anything outside of
    'radius' * RADIUS_TOLERANCE will be considered outside of the radius. The
    reasoning is that find_closest() will tolerate a series of poor matches
    when the GoPro and Wahoo GPX paths briefly diverge due to GPS inaccuracy.

    """

    if search not in ["first_in_radius", "last_in_radius", "best_in_radius"]:
        raise ("find_closest bad search argument")

    if not radius:
        radius = DEFAULT_RADIUS

    logging.debug("find_closest, radius = %f" % (radius))

    in_radius = False
    mindist, minidx = None, len(refs) - 1

    for idx in range(start, len(refs)):
        ref = refs[idx]
        xdist = dist(p, ref)
        logging.debug("find_closest idx %d, d = %f" % (idx, xdist))

        # we got within radius distance of point p
        if xdist < RADIUS_MIN or xdist < radius:
            if not in_radius:
                in_radius = True
                logging.debug("xdist < radius, in_radius")
            if search == "first_in_radius":
                logging.debug(
                    "xdist < radius, search == 'first' returning with idx %d " % (idx)
                )
                return idx

        # we left the radius after having been in it
        elif in_radius:
            logging.debug("left radius")
            if search == "last_in_radius":
                logging.debug(
                    "left radius, search == 'last', returning with %d" % (idx - 1)
                )
                return idx - 1
            elif search == "best_in_radius":
                logging.debug(
                    "left radius, search == 'best_abort', returning with %d" % (minidx)
                )
                return minidx
            in_radius = False

        if mindist is None or xdist < mindist:
            mindist = xdist
            minidx = idx
            logging.debug("new mindist = %f at idx %d" % (xdist, idx))

        if xdist > RADIUS_MIN and xdist > (radius * RADIUS_TOLERANCE):
            logging.debug("out of radius tolerance; abort")
            break

    logging.debug("return minidx %d " % (minidx))
    return minidx


LOOKBACK = 10


def gpxcomment(points, ref_points, force_timezone=False, pause_snap=DEFAULT_PAUSE_SNAP):
    # build an array of indices in ref_points[] that correspond to the start of
    # a pause
    pauses = find_pauses(ref_points, pause_snap=pause_snap)
    logging.debug("Pauses = " + str(pauses))

    # as we traverse points and we match to a pause, pause_idx is the index in
    # pauses[] currently in, note that ref_points[pauses[pause_idx]] is the
    # start of the pause
    pause_idx = None

    # starting time of the current pause
    pause_start_at = None

    # once out of pause, pause_duration is the length of the most recently
    # processed pause
    pause_duration = None

    # while in pause, accumulate points from points[] that are spent in that
    # pause; these are later used to distribute among the pause time.
    pause_points = []

    # the most recently matched point in ref_points[]
    idx = 0

    # the idx from the previous iteration
    prev_idx = 0

    # the cumulative distance traveled so far
    cumulative_dist = 0

    # the first point after the most recently processed pause; this is used to
    # prevent lookback past a processed pause
    backstop_idx = 0

    # look up timezone of first point
    to_zone_str = None
    if not force_timezone:
        tf = TimezoneFinder()
        to_zone_str = tf.timezone_at(lng=points[0].longitude, lat=points[0].latitude)

    xpoints, processed_pauses = [], []
    for pidx, point in enumerate(points):
        logging.debug(
            "Processing pidx %d, point %s, prev_idx = %s"
            % (pidx, str(point), str(prev_idx))
        )

        # distance of previous point/reference match
        prev_dist = None
        if pidx > 0:
            prev_dist = dist(points[pidx - 1], ref_points[prev_idx])

        # find the best distance match; be willing to match to the past, though
        # not further back than idx-LOOKBACK, and certainly not beyond the
        # 0-index.
        idx = find_closest(
            point, ref_points, max(0, backstop_idx, idx - LOOKBACK), prev_dist
        )

        # possibly snap it to the next pause
        snap_idx = snap_to_pause(pauses, ref_points, idx, pause_snap=pause_snap)
        logging.debug(
            "idx %d (dist = %f), snap_idx %d (dist = %f)"
            % (
                idx,
                dist(point, ref_points[idx]),
                snap_idx,
                dist(point, ref_points[snap_idx]),
            )
        )

        # don't snap to a pause if a) already in a pause or b) this pause has
        # already been snapped to previously
        if snap_idx in processed_pauses and not pause_start_at:
            logging.debug(
                "Skipping snap_idx %d because already processed in %s"
                % (snap_idx, str(processed_pauses))
            )

        # snap to this pause
        else:
            idx = snap_idx
            logging.debug(
                "idx -> snap_idx %d, dist = %f" % (idx, dist(point, ref_points[idx]))
            )

        # we entered or are (still) in a pause
        if idx in pauses:
            # figure out whether the pause we snapped to is the same as we were
            # in already; this handles the case where two consecutive pauses
            # were very close to each other
            new_pause_idx = pauses.index(idx)

            # we are starting a new pause
            if not pause_start_at:
                pause_idx = new_pause_idx
                processed_pauses.append(idx)
                pause_start_at = ref_points[pauses[pause_idx]].time
                pause_end_at = ref_points[pauses[pause_idx] + 1].time
                pause_duration = (pause_end_at - pause_start_at).total_seconds()
                logging.debug(
                    "Start of pause_idx %d, pause at %s, end of pause %s, duration %d "
                    % (pause_idx, pause_start_at, pause_end_at, pause_duration)
                )

            # we are entering a new pause, so we need to "glue" this new pause
            # to the previous pause.
            elif new_pause_idx != pause_idx:
                pause_idx = new_pause_idx
                processed_pauses.append(idx)
                pause_end_at = ref_points[pauses[pause_idx] + 1].time
                pause_duration = (pause_end_at - pause_start_at).total_seconds()
                logging.debug(
                    "Started consecutive pause_idx %d, still started pause at %s, new end of pause %s, new duration %d "
                    % (pause_idx, pause_start_at, pause_end_at, pause_duration)
                )

            logging.debug(
                "idx = %d, dist = %f, pause_idx = %s"
                % (idx, dist(point, ref_points[idx]), pause_idx)
            )
            backstop_idx = pause_idx + 1

        # came out of pause; now we know how long the pause was
        elif pause_start_at:
            logging.debug(
                "Came out of pause; buffered points = "
                + str(len(pause_points))
                + " over "
                + str(pause_duration)
                + " seconds "
            )

            # add all the buffered points while smoothing out the paused time
            for buffered_idx, buffered_point in enumerate(pause_points):
                time = pause_start_at + timedelta(
                    seconds=(
                        (float(pause_duration) / float(len(pause_points)))
                        * buffered_idx
                    )
                )
                logging.debug("Fake time for buffered point: %s" % (time))
                mpoint = create_modified_point(
                    buffered_point, time, to_zone_str, 0, cumulative_dist
                )
                xpoints.append(mpoint)
            pause_start_at = None
            pause_points = []

        # while in pause, don't write to output; we are waiting to find out where the pause stops
        if pause_start_at:
            logging.debug("Pause buffering pidx %03d" % (pidx))
            pause_points.append(point)
            continue

        logging.info(
            "gpxcomment: %05d / %05d (%02d%%) => %05d: dist %f @ %s"
            % (
                pidx,
                len(points),
                (((pidx + 1) / len(points)) * 100),
                idx,
                dist(point, ref_points[idx]),
                ref_points[idx].time,
            )
        )

        # calculate speed if not specified
        # do it the simple way, but possible to include earth's
        # curvature: https://stackoverflow.com/questions/45840118/how-do-i-calculate-speed-from-a-gpx-file-if-the-speed-tag-itself-is-not-given
        if ref_points[idx].speed:
            speed = ref_points[idx].speed
        else:
            if idx == 0:
                speed = 0
            else:
                xdist = dist(ref_points[idx - 1], ref_points[idx])
                xdiff = diff(ref_points[idx - 1], ref_points[idx])
                speed = (xdist * 1000) / xdiff

        # track cumulative distance
        if prev_idx:
            for i in range(prev_idx, idx):
                cumulative_dist += dist(ref_points[i], ref_points[i + 1])
        prev_idx = idx

        # add the point to the output track
        mpoint = create_modified_point(
            point, ref_points[idx].time, to_zone_str, speed, cumulative_dist
        )
        xpoints.append(mpoint)

    return xpoints
