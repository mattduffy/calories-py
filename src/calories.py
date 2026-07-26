import math
import random
from functools import reduce

# Some constants are defined for use in the entire module.

# Terrain coeffcients to characterize walking surface.
TERRAIN_COEFFCIENTS = {
    "BLACKTOP": 1.0, # Paved road / treadmill
    "DIRT": 1.1,     # Dirt path, packed trail
    "LIGHT": 1.2,    # Light off-trail, grass
    "SOFT": 1.5,     # Soft sand, deep grass, loose gravel
    "HEAVY": 1.8     # Snow, heavy brush, swamp
}

# Defaults for smoothing out jittery GPS elevation data.
SMOOTH_DEFAULT = True
SMOOTH_DEFAULT_WINDOW = 5

# Maximum plausible walking speed (m/s).
# Speeds higher than this are clamped to this value.
MAX_SPEED_MS = 4.0

# Minimum segment distance. Filters out GPS jitter.
MIN_SEGMENT_DIST_M = 0.5

# Conversion: 1Kcal = 4184 joules
JOULES_PER_KCAL = 4184

# Minimum Mechanics derived constants:
# Table 4, Ludlow & Weyland 2017
MM_COEFFICIENTS = {
    "C1": 0.32,              # grade influence on minimum walking metabolic rate
    "C2": 0.19,              # grade influence on speed-dependent walking metabolic rate
    "C3": 2.66,              # velocity squared coefficient
    "VO2_WALK_MIN": 3.28,    # ml O2 kg-total^-1 min^-1, minimum walking metabolic rate
    "C_DECLINE": 0.73        # fraction of level-grade walking cost applied in decline
}


# Mean measured supine resting metablic rate across all 32 study subjects (ml O2 kg-body^-1 min^-1).
# Used as the default VO2-rest term if no subject-specific resting metabloic rate is given.
# Ludlow & Weyland 2017
DEFAULT_RESTING_VO2 = 3.05

# Standard caloric equivalent of oxygen: ~5kcal per liter O2 per 1000ml.  Expressed here per ml
# for direct multiplication against VO2 rates in ml O2 min^-1.
KCAL_PER_ML_O2 = 0.005

# Convert a number of milliseconds to seconds.
def m2s(milliseconds: int) -> int:
    """Convert a number of milliseconds to seconds.

    Args:
        milliseconds (int): Time in milliseconds.

    Returns:
        int: Time converted into seconds.
    """
    # print(f"milliseconds type: {type(milliseconds)}")
    seconds = int(milliseconds / 1000)
    # print(f"seconds {seconds}, type: {type(seconds)}")
    return seconds


# Convert a number of milliseconds to minutes.
def m2m(milliseconds: int) -> float:
    """Convert a number of milliseconds to minutes.

    Args:
        milliseconds (int): Time in milliseconds.

    Returns:
        float: Time converted into minutes.
    """
    # print(f"milliseconds type: {type(milliseconds)}")
    # print(f"milliseconds -> seconds: {m2s(milliseconds)}")
    minutes = milliseconds / 60000
    # print(f"minutes type: {type(minutes)}")
    return minutes


# Convert radians to compass degress.
def rads(degrees: float) -> float:
    """Convert compass degrees to radians.

    Args:
        degrees (float): Compass degress value.

    Returns:
        float: The calculated radians value.
    """
    return degrees * (math.pi / 180)


def pointDistance(p1: dict, p2: dict, u = "metric") -> float:
    """Calculate the Haversine distance between two GPS points.

    Args:
        p1 (dict): Dictionary containing latitude and longitude values.
        p2 (dict): Dictionary containing latitude and longitude values.
        u (string): String value indicating unit system to use.

    Returns:
        float: The Haversine distance between GPS points p1 and p2.

    Raises:
        ValueError: if p1 argument is missing longitude or latitude values.
        ValueError: if p2 argument is missing longitude or latitude values.
    """
    if "longitude" not in p1 or "latitude" not in p1:
        raise ValueError(f"Point p1 argument is requires longitude and latitude values.")
    if "longitude" not in p2 or "latitude" not in p2:
        raise ValueError(f"Point p2 argument is requires longitude and latitude values.")
    earthRadiusKm = 6371
    earthRadiusMeters = 6371000
    earthRadiusMiles = 3959
    _u = u.lower()
    r = None
    if _u == 'm' or _u == 'meters':
        r = earthRadiusMeters
    elif _u == 'km' or _u == 'kilometers':
        r = earthRadiusKm
    elif _u == 'mi' or _u == 'miles' or _u == 'imperial':
        r = earthRadiusMiles
    else:
        r = earthRadiusMeters
    #print(r, _u)
    dLat = rads(p2['latitude'] - p1['latitude'])
    dLon = rads(p2['longitude'] - p1['longitude'])
    lat1 = rads(p1['latitude'])
    lat2 = rads(p2['latitude'])
    a = math.sin(dLat / 2) * math.sin(dLat / 2) \
        + math.sin(dLon / 2) * math.sin(dLon / 2) * math.cos(lat1) * math.cos(lat2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return c * r


# Calculate the difference in altitude between two points.
def calculateVerticalInterval(alt1: float, alt2: float) -> float:
    """Calculate the difference in altitude between two points.

    Args:
        alt1 (float): First altitude value.
        alt2 (float): Second altitude value.

    Returns:
        float: Altitude difference.
    """
    return alt2 - alt1


# Calculate the slope between two points.
def calculateSlopeGrade(point1: dict, point2: dict) -> dict:
    """Calcuate the slope between two GPS points.

    Args:
        point1 (dict): Dictionary with longitude and latitude properties.
        point2 (dict): Dictionary with longitude and latitude properties.

    Returns:
        dict: Dictionary with grade and angleDegrees properties.
    """
    horizontalDistance = pointDistance(point1, point2)
    verticalDistance = calculateVerticalInterval(point1["altitude"], point2["altitude"])
    if horizontalDistance == 0:
        return { "grade": math.inf, "angleDegrees": 90 }
    slope = verticalDistance / horizontalDistance
    grade = slope * 100
    angle = math.atan(slope) * 180
    return {
        "grade": grade,
        "angleDegrees": angle / math.pi
    }


# Apply a simple rolling-average smoother to the altitude values in a coordinates array.
def smoothAltitude(coords: List[List[float]], windowSize: int = SMOOTH_DEFAULT_WINDOW) -> List[List[float]]:
    """Apply a simple rolling-average smoothing function to the altitude values in a coordinates array.
        Raw GPS altitude can have +-5 to 15 m of noise, which can create artificial grade spikes that inflate calorie estimates.

    Args:
        coords (List[List[float]]: List of coordinate arrays.
        windowSize (int): Number of points to average (odd number recommended).

    Returns:
        List[List[float]]: New coordinates array with smoothed altitudes.
    """
    half = math.floor(windowSize / 2)
    # print(f"windowSize: {windowSize}, half: {half}")
    smoothed = list()
    i = 0
    n = len(coords)
    # print(f"coords length: {n}")
    while i < n:
        # print(f"\tstarting loop: {i}")
        start = max(0, i - half)
        end = min(n - 1, (i + half) + 2) # + 2 because slice end index is non-inclusive
        # print(f"\tstart: {start}, end: {end}")
        slice = coords[start:end]
        # print(f"\tslice (length {len(slice)}): {slice}\n")
        validAlts = [x[3] for x in slice if x[3] is not None]
        # print(f"\tvalidAlts: {validAlts}")
        averageAltitude = reduce(lambda acc, curr: acc + curr, validAlts, 0) / len(validAlts) if len(validAlts) > 0 else slice[3]
        smoothed.append([coords[i][0], coords[i][1], coords[i][2], averageAltitude, coords[i][4], coords[i][5]])
        # print(f"\tsmoothed altitude: {averageAltitude}, {validAlts}\n")
        i = i + 1
    return smoothed


# Simple MET based calorie estimate.
def simpleCalories(minutes: int = 1, weights: dict = { "body": 0, "ruck": 0, "water": 0 }, MET: float = 7.5) -> float:
    """The simplest calorie estimating function.  Calculates the ratio of energy spent per unit time during a specific
    physical activity to a reference value of 3.5 ml O2 / (kg·min).

    Args:
        minutes (float): Time spent expending energy, in minutes.
        weights (dict): Collection of weight values, in kilograms.
        MET (float): The Metabolic Equivalent Task number of activity.

    Raises:
        ValueError: If minutes is not a valid, positive number.
        ValueError: If weights.body is not a valid, positive number.
        ValueError: If MET is not a valid, positive number.
        
    Returns:
        float: Number of calories burned.
    """
    if minutes <= 0 or minutes is None:
        raise ValueError(f"Minutes must be a positive, finite number. (Supplied {minutes})")
    if weights["body"] <= 0 or weights["body"] is None:
        raise ValueError(f"Body weight must be a positive, finite number.  (Supplied {weights["body"]}")
    if MET <= 0 or MET is None:
        raise ValueError(f"MET must be a positive, finite number.  (Supplied {MET})")
    COMBINED = weights["body"] + weights["ruck"] + weights["water"]
    # print(COMBINED)
    return ((MET * 3.5 * COMBINED) / 200) * minutes
    

# Corrective factor for downhill (G < 0) segments of the hike.
def santeeCorrective(W: float, L: float, V: float, G: float, n: float) -> float:
    """Corrective factor for downhill (G < 0) segments of the hike.

    Args:
        W (float): Body weight measured in kg.
        L (float): Load weight measured in kg.
        V (float): Walking speed in m/s.
        G (float): Hill grade as a percentage (e.g 10 for 10% incline, -5 for decline).
        n (float): Terrain characterization coefficient.

    Returns:
        float: Downhill corrective factor in Watts.
    """
    return n * ( \
        (G * (W + L) * V) / 3.5 \
        - ((W + L) * (((G + 6) ** 2) / W)) \
        + (25 * (V ** 2)) \
    )


# Calculate the metabolic rate (Watts) using Pandolf-Santee predictive model.
def pandolfMetabolicRate(W: float, L: float, V: float, G: float, n: float) -> float:
    """Calculate the metabolic rate (Watts) using Pandolf-Santee predictive model.

    Args:
        W (float): Body weight measured in kg.
        L (float): Load weight measured in kg.
        V (float): Walking speed in m/s.
        G (float): Hill grade as a percentage (e.g 10 for 10% incline, -5 for decline).
        n (float): Terrain characterization coefficient.

    Returns:
        float: Metabolic rate in Watts (should always be >= 0).
    """
    if V <= 0:
        return 0
    loadRatio = L / W
    M = 1.5 * W \
        + 2 * (W + L) * loadRatio ** 2 \
        + n * (W + L) * (1.5 * V ** 2 + 0.35 * V  * G)
    correction = 0
    if G < 0:
        correction = santeeCorrective(W, L, V, G, n)
    # the equation can return negative values on steep descents so clamp to 0.
    return max(0, M - correction)


# Processes a single segment (two consecutive GPS points and returns metabolic and distance data.
def processPandolfSegment(point1: List, point2: List, W: float, L: float, H2O: float, n: float) -> dict | None:
    """Processes a single segment (two consecutive GPS points and returns metabolic and distance data.

    Args:
        point1 (List): [longitude, latiude, heading, altitude, accuracy, timestamp]
        point1 (List): [longitude, latiude, heading, altitude, accuracy, timestamp]
        W (float): Body weight measured in kg.
        L (float): Load weight carried measured in kg.
        H20 (float): Water weight carried measured in kg.
        n (float): Terrain characterization coefficient.

    Returns:
        dict | None: Segment result or None if the segment should be skipped.
    """
    lon1, lat1, _, alt1, _, t1 = point1
    lon2, lat2, _, alt2, _, t2 = point2
    p1 = { "longitude": lon1, "latitude": lat1, "altitude": alt1 }
    p2 = { "longitude": lon2, "latitude": lat2, "altitude": alt2 }
    horizontalDistance = pointDistance(p1, p2)
    durationSec = m2s(t2 - t1)
    # skip GPS jitter, stationary points, or out-of-order timestamps
    if durationSec <= 0 or horizontalDistance < MIN_SEGMENT_DIST_M:
        return None
    slopeGrade = calculateSlopeGrade(p1, p2)
    grade = slopeGrade["grade"]
    altitudeDiff = alt2 = alt1
    # Derived speed, clamped to MAX_SPEED_MS to guard against GPS outliers.
    speed = min(horizontalDistance / durationSec, MAX_SPEED_MS)
    # Metabolic rate (Watts) for this segment.
    metabolicRateWatts = pandolfMetabolicRate(W, L + H2O, speed, grade, n)
    # Energy expended = power * time (joules), converted to kcal.
    kcal = (metabolicRateWatts * durationSec) / JOULES_PER_KCAL
    return {
        "horizontalDistance": horizontalDistance,
        "altitudeDiff": altitudeDiff,
        "grade": grade,
        "speed": speed,
        "durationSec": durationSec,
        "metabolicRateWatts": metabolicRateWatts,
        "kcal": kcal
    }


# Use the Pandolf-Santee predictive model to calculate the total (and per-segment) calorie expenditure for a GPS track.
def pandolfCalories(coords: List[List[float]] = [], options: dict = {}) -> dict:
    """Use the Pandolf-Santee predictive model to calculate the total (and per-segment) calorie expenditure for a GPS track.

    Args:
        coords (List[List[float]]): GPS coordinates array.  Each element:
            [longitude, latitude, heading, altitude (m), accuracy (m), timestamp (ms)]
        options (dict): Options
        options["bodyWeightKg"] (float): Body weight in kg (required).
        options["loadKg"] = 0 (float): Load/pack weight in kg (optional).
        options["waterKg"] = 0 (float): Water weight in kg carried (optional).
        options["terrain"] = 1.1 (float): Terrain coefficient (optional).  Use TERRAIN_COEFFICIENTS.
        options["smooth"] = True (Boolean): Whether to smooth GPS altitude values (optional).
        options["smoothWindow"] = 5 (int): Rolling average window size for smoothing (optional).
        options["returnSegments"] = False (Boolean): Return array of all segments calculated (optional)?

    Raises:
        ValueError: If coords array contains less than 2 items.
        ValueError: If required body weight is < 0, null, or otherwise invalid.

    Returns:
        dict: Results
        {
            totalKcal,        # Total calories burned.
            totalDistanceM,   # Total horizontal distance (meters).
            totalDurationSec, # Total elapsed time (seconds).
            avgSpeedMs,       # Average speed (m/s).
        }
    """
    bodyWeightKg = options.get("bodyWeightKg", 0)
    loadKg = options.get("loadKg", 0)
    waterKg = options.get("waterKg", 0)
    terrain = options.get("terrain", 1.1)
    smooth = options.get("smooth", True)
    smoothWindow = options.get("smoothWindow", SMOOTH_DEFAULT_WINDOW)
    returnSegments = options.get("returnSegments", False)
    if len(coords) < 2:
        raise ValueError(f"The coordinates array needs at least 2 elements, {len(coords)} provided.")
    if not bodyWeightKg or bodyWeightKg <= 0:
        raise ValueError(f"options.bodyWeightkg is required and must be a positive number, {bodyWeightKg} provided.")
    track = smoothAltitude(coords, smoothWindow) if smooth else coords
    # print(len(track))
    segments = []
    totalKcal = 0
    totalDistanceM = 0
    totalDurationSec = 0
    for i in range(0, len(track)):
        seg = processPandolfSegment(track[i - 1], track[i], bodyWeightKg, loadKg, waterKg, terrain)
        if seg:
            totalKcal += seg["kcal"]
            totalDistanceM += seg["horizontalDistance"]
            totalDurationSec += seg["durationSec"]
            segments.append(seg)

    avgSpeedMs = (totalDistanceM / totalDurationSec) if (totalDurationSec > 0) else 0
    results = {
        "totalKcal": totalKcal,
        "totalDistanceM": totalDistanceM,
        "totalDurationSec": totalDurationSec,
        "avgSpeedMs": avgSpeedMs
    }
    if returnSegments:
        results["segments"] = segments
    return results


