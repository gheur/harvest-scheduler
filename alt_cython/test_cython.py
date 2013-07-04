from scheduler import schedule
import numpy as np

if __name__ == '__main__':

    stand_data = np.array([  # list of stands
        [  # list of stand STATES
            [  # list of stand state time periods
                [12, 6, 5],  # <-- list of stand state time period variables
                [12, 0, 6],
                [3, 7, 4],
            ],
            [
                [11, 2, 2],
                [2, 1, 6],
                [10, 9, 3],
            ],
        ],
        [  # stand 2
            [  # state 1
                [12, 6, 5],  # time period 1
                [1, 0, 6],
                [1, 7, 4],
            ],
            [  # state 2
                [11, 2, 2],
                [3, 1, 6],
                [9, 9, 3],
            ],
        ],
    ])


    # consistently generate a random set
    np.random.seed(42)
    stand_data = np.random.randint(10, size=(37,25,20,3))
    stand_data = stand_data.astype(float)

    # pick a strategy for each stand state time period variable
    strategies = ['cumulative_maximize', 'evenflow', 'cumulative_cost']
    """
    cumulative_maximize : target the absolute highest cumulative value

    evenflow            : minimize variance around a target

    cumulative_cost     : treated as cost; sum over all time periods
    """

    # todo .. flow must specify weight of missed target vs 
    targets = [
        None,       # maximized variables don't have target; target is calculated
        [5, 5, 5],  # flow_target is an array same length as time period
        None        # maximize and costs variables don't need an explicit target
    ]

    weights = [5, 100, 1]

    adjacency = []  # need to define which variable is considered ("harvest")
     # and when state is changed, check the adjacent stands for each time period
     # penalize/avoid if they have overlapping harvests.

    mandatory_states = []  # when changing state, make sure these don't get altered

    for i in range(1):
        optimal_stand_states = schedule(
            stand_data,
            strategies,
            targets,
            weights,
            adjacency
        )

        print optimal_stand_states