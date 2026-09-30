import math
from cross_track_distance import cross_track_distance 

def degs2Rads(degs: float) -> float:
    return degs * math.pi/180

def rads2Degs(rads: float) -> float:
    return rads * 180 / math.pi

def ramer_douglas_peucker(points: list[list[float]] = (), epsilon: float = 2.0) -> list[list[float]]:
    """A cartographic generalization algorithm to reduce the number of points in a 
       curve, composed of line segments, into a similar curve consisting of fewer points.

    Args:
        points (list[list[float]]): A list of gps coordinate arrays.
        epsilon (float): A distance threshold value > 0.

    Returns:
        list[list[float]]: A new list of gps points, of equal length as points, or fewer.
    """
    max_distance = 0
    index = 0
    end = len(points)
    #print(f'len(points): {len(points)}, epsilon: {epsilon}, max_distance: {max_distance}, index: {index}, end: {end}')
    for i in range(1, end - 1):
        #print(f'({i}) lon {points[i][0]}, lat {points[i][1]}')
        #print(f'point[i: {i}], (points[0], points[end: {end - 1}]')
        d = abs(cross_track_distance(points[i], (points[0], points[end - 1])))
        #print(f'point[{i}] has perpendicular distance {d} from points polyline.')
        if (d > max_distance):
            index = i
            max_distance = d
            #print(f'\tnew max_distance {max_distance}, at index {index}')
        #print('\n')
        
    if (max_distance > epsilon):
        # print(f'max_distance {max_distance} > epsilon {epsilon}')
        # print(f'making recursive calls')
        # recursive call to ramer_douglas_peucker()
        # left half spans points[0]..points[index]; right half spans points[index]..points[end - 1].
        # The pivot point[index] is shared by both halves.
        recResultsLeft = list(ramer_douglas_peucker(points[0:index + 1], epsilon))
        recResultsRight = list(ramer_douglas_peucker(points[index:end], epsilon))

        # combine the two results lists, dropping the shared pivot (last of left == first of right)
        # print('recursively combined simplified_list')
        #print(f'left {len(recResultsLeft)}', recResultsLeft, recResultsLeft[:-1])
        #print(f'right {len(recResultsRight)}', recResultsRight)
        simplified_list = recResultsLeft[:-1] + recResultsRight
        # print(f'combined, {simplified_list}')
    else:
        # print(f'max_distance {max_distance} !> epsilon {epsilon}')
        simplified_list = list((points[0], points[end - 1]))
        
    return simplified_list
