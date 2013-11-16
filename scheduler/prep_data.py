import numpy as np
import json
import math


def from_random(stands, mgmts, timeperiods, numvars):
    # consistently generate a random set
    np.random.seed(42)
    # 4D: stands, mgmts, time periods, variables
    stand_data = np.random.randint(4, 14, size=(stands, mgmts, timeperiods, numvars))
    axis_map = {'mgmt': [(x, '00') for x in range(stand_data.shape[1])]}
    valid_mgmts = [[] for x in range(stand_data.shape[0])]

    return stand_data, axis_map, valid_mgmts


def from_demo():
    stand_data = np.array(
        [  # list of stands
            [  # list of rxs
                [  # list of time periods
                    [12, 6, 5],  # <-- list of variable values
                    [12, 0, 6],
                    [3, 7, 4],
                ],
                [
                    [11, 2, 2],
                    [2, 1, 6],
                    [10, 9, 3],
                ],
            ],
            [   # stand 2
                [   # rx 1
                    [12, 6, 5],  # time period 1
                    [1, 0, 6],
                    [1, 7, 4],
                ],
                [   # rx 2
                    [11, 2, 2],
                    [3, 1, 6],
                    [9, 9, 3],
                ],
            ],
        ]
    )
    return stand_data


def bbox_center(bbox):
    x = (bbox[0] + bbox[2])/2.0
    y = (bbox[1] + bbox[3])/2.0
    return x, y


def mercator_to_lonlat(pt):
        "Converts XY point from Spherical Mercator EPSG:900913 to lat/lon in WGS84 Datum"
        originShift = 2 * math.pi * 6378137 / 2.0  # 20037508.342789244
        lon = (pt[0] / originShift) * 180.0
        lat = (pt[1] / originShift) * 180.0

        lat = 180 / math.pi * (2 * math.atan(math.exp(
                                             lat * math.pi / 180.0)) - math.pi / 2.0)
        return lon, lat


def calculate_cost():
    # ###################################################################
    # # Calculate actual cost

    # poly = shapes[i]
    # # TODO assert poly is single part
    # wkt = "POLYGON((%s))" % (",".join(["%f %f" % (x, y) for (x, y) in poly.points]))

    # #print cond, line['year'], rx, offset, "Cut type", cut_type, "PartialCut", PartialCut

    # if PartialCut is not None:
    #     cost_args = (
    #         # stand info
    #         acres, elev, slope, wkt,
    #         # harvest info
    #         float(line['CH_TPA']), float(line['CH_CF']),
    #         float(line['SM_TPA']), float(line['SM_CF']),
    #         float(line['LG_TPA']), float(line['LG_CF']),
    #         float(line['CH_HW']), float(line['SM_HW']), float(line['LG_HW']),
    #         PartialCut,
    #         # routing info
    #         landing_coords, haulDist, haulTime, coord_mill
    #     )

    #     if sum(cost_args[4:10]) == 0:
    #         #print "No chip, small or log trees but cut indicated ... how did we get here?"
    #         #print cond, line['year'], rx, offset, "Cut type", cut_type, "PartialCut", PartialCut
    #         vars.append(0.0)
    #     else:
    #         try:
    #             result = main_model.cost_func(*cost_args)
    #             #print "Cost model run successfully"
    #             cost = result['total_cost']
    #             vars.append(cost)
    #         except ZeroDivisionError:
    #             print "\nZeroDivisionError:\n"
    #             print cost_args
    #             print "--------------"
    #             vars.append(0.0)
    # else:
    #     # No cut == no cost
    #     # print "No cut, no cost"
    #     vars.append(0.0)

    # ###################################################################
    pass


def calculate_metrics(line, stand):
    acres = stand['acres']
    slope = stand['slope']
    data = []
    try:
        carbon = float(line['total_stand_carbon']) * acres
        timber = float(line['removed_merch_ft3']) * acres / 1000.0  # mbf
        owl_acres = float(line['NSONEST']) * acres
        fire_code = float(line['FIREHZD'])
    except ValueError:
        return  # TODO 

    data.append(timber)
    data.append(timber)  # include another timber column for even flow
    data.append(carbon)
    data.append(owl_acres)

    # Determine areas with high fire risk
    # 0 = very low risk, 1 = low risk, 2 = medium risk
    # 3 = medium-high risk, 4 = high risk
    if fire_code > 3: 
        fire_acres = acres
    else:
        fire_acres = 0
    data.append(fire_acres)

    # Use slope as a stand-in for cost
    try:
        cut_type = line['CUT_TYPE']
        cut_type = int(float(cut_type))
    except ValueError:
        # no harvest so don't attempt to calculate
        cut_type = 0

    # PartialCut(clear cut = 0, partial cut = 1)
    PartialCut = None
    if cut_type == 3:
        PartialCut = 0
    elif cut_type in [1, 2]:
        PartialCut = 1

    if PartialCut is None:  # no harvest
        data.append(0)
    elif PartialCut == 0:  # clear cut = use slope as cost proxy
        data.append(slope)
    elif PartialCut == 1:  # partial cut = use half slope as cost proxy
        data.append(slope/2) 

    return data


def get_stands(shp, default_site=2):
    import shapefile
    # TODO validate fields
    sf = shapefile.Reader(shp)
    fields = [x[0] for x in sf.fields[1:]]
    for record in sf.iterRecords():
        dd = dict(zip(fields, record))
        raw_restricted_rxs = dd['rx']
        try:
            dd['restricted_rxs'] = [int(x) for x in raw_restricted_rxs.split(",")]
        except ValueError:
            dd['restricted_rxs'] = None
        del dd['rx']
        try:
            dd['site'] = int(dd['site'])
        except KeyError:
            dd['site'] = default_site
        dd['acres'] = dd['ACRES']
        dd['slope'] = dd['SLOPE_MEAN']

        yield dd      


def handle_error(inputs):
    raise Exception("\nNo fvs outputs found for the following case (check your input shp):\n%s" % json.dumps(inputs, indent=2))


def prep_shp_db(shp, db, variant="WC", climate="Ensemble-rcp60", cache=False, verbose=False):
    import sqlite3
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check cache
    if cache:
        try:
            stand_data = np.load('cache.array.npy')
            axis_map = json.loads(open('cache.axis_map').read())
            valid_mgmts = json.loads(open('cache.valid_mgmts').read())
            print "Using cached data to reduce calculation time..."
            return stand_data, axis_map, valid_mgmts
        except:
            pass  # calculate it

    # find all rx, offsets
    axis_map = {'mgmt': []} 
    sql = """
        SELECT rx, offset
        FROM trees_fvsaggregate
        GROUP BY rx, offset
    """
    for row in cursor.execute(sql):
        axis_map['mgmt'].append((row['rx'], row['offset']))

    valid_mgmts = [] # 2D array holding valid mgmt ids for each stand
    property_stands = []

    for stand in get_stands(shp):
        if verbose:
            print stand['cond'], stand

        temporary_mgmt_list = []
        stand_mgmts = []

        for mgmt_id, mgmt in enumerate(axis_map['mgmt']):
            rx, offset = mgmt
            if verbose:
                print "\t", rx, offset

            inputs = {
                'var': variant, 
                'rx': rx, 
                'cond': stand['cond'],
                'site': stand['site'],
                'climate': climate,
                'offset': offset }

            sql = """
              SELECT *
              FROM trees_fvsaggregate
              WHERE var = '%(var)s'
              AND rx = %(rx)d
              AND cond = %(cond)d
              AND site = %(site)d
              AND climate = '%(climate)s'
              AND "offset" = %(offset)d
              ORDER BY year
            """ % inputs

            empty = True
            mgmt_timeperiods = []
            for row in cursor.execute(sql):
                empty = False
                year = row['year']

                yeardata = calculate_metrics(row, stand)
                if verbose:
                    print "\t\t", year, yeardata

                assert len(yeardata) == 6
                mgmt_timeperiods.append(yeardata)

            if empty:
                handle_error(inputs)

            if stand['restricted_rxs']:
                if rx in stand['restricted_rxs']:
                    temporary_mgmt_list.append(mgmt_id)
            else:
                temporary_mgmt_list.append(mgmt_id)

            assert len(mgmt_timeperiods) == 20
            stand_mgmts.append(mgmt_timeperiods)

        if len(temporary_mgmt_list) == 0:
            handle_error({'rxs': stand['restricted_rxs']})

        valid_mgmts.append(temporary_mgmt_list)
        property_stands.append(stand_mgmts)

    arr = np.array(property_stands)


    # caching
    np.save('cache.array', arr)
    with open('cache.axis_map', 'w') as fh:
        fh.write(json.dumps(axis_map, indent=2))
    with open('cache.valid_mgmts', 'w') as fh:
        fh.write(json.dumps(valid_mgmts, indent=2))

    return arr, axis_map, valid_mgmts
