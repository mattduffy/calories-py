import math

def degs2Rads(degs: float) -> float:
    return degs * math.pi/180

def rads2Degs(rads: float) -> float:
    return rads * 180 / math.pi

def cross_track_distance(point: list[float], track: list[list[float]], scale='m') -> float:
    """Calculate the perpendicular distance (in meters) of a gps point from a track (polyline
        segment) consisting of two other gps points.

    Args:
        point (list[float]): A list containing gps coordinates [lon, lat].
        track (list[list[float]]): A two point polyline list [[lon, lat], [lon, lat]].
        scale (str): Sets the unit size of the track distance value, either 'km' or 'm'.

    Returns:
        float: The perpendicular distance of the point from the track (line segment).
    """
    # Convert all longitudes and latitudes from degrees to radians
    point_lon, point_lat = math.radians(point[0]), math.radians(point[1])
    start_lon, start_lat = math.radians(track[0][0]), math.radians(track[0][1])
    end_lon, end_lat = math.radians(track[1][0]), math.radians(track[1][1])

    # Calculate the angular distance from start to point
    # Ensure the argument is within the domain of acos
    acos_argument = math.sin(start_lat) * math.sin(point_lat) + math.cos(start_lat) * math.cos(point_lat) * math.cos(point_lon - start_lon)
    acos_argument = max(-1, min(1, acos_argument))  # Clamp the argument between -1 and 1
    delta_sigma = math.acos(acos_argument)

    # Calculate the bearing from start to point and start to end
    theta_point = math.atan2(math.sin(point_lon - start_lon) * math.cos(point_lat),
                             math.cos(start_lat) * math.sin(point_lat) - math.sin(start_lat) * math.cos(point_lat) * math.cos(point_lon - start_lon))
    theta_end = math.atan2(math.sin(end_lon - start_lon) * math.cos(end_lat),
                           math.cos(start_lat) * math.sin(end_lat) - math.sin(start_lat) * math.cos(end_lat) * math.cos(end_lon - start_lon))

    # Calculate the cross track distance
    cross_track_dist = math.asin(math.sin(delta_sigma) * math.sin(theta_point - theta_end))
    earth_radius_in_km = 6371
    scale = 1 if (scale == 'km') else 1000
    # print(f'scale = {scale}')
    cross_track_dist = cross_track_dist * (earth_radius_in_km * scale)
    return cross_track_dist
