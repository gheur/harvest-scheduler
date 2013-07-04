from libc cimport math
import random
cimport numpy as np
import numpy as np
cimport cython
ctypedef np.float_t DTYPE_t

cdef extern from "math.h":
    double exp(double x)


@cython.boundscheck(False)
def schedule(
        np.ndarray[DTYPE_t, ndim=4] data,
        strategies, 
        weights,
        variable_names,
        adjacency,
        valid_states,
        float temp_min=0.01, 
        float temp_max=1000, 
        int steps=50000,
        int report_interval=1000):
    cdef int num_stands = data.shape[0]
    cdef int num_states = data.shape[1]
    cdef int num_periods = data.shape[2]
    cdef int num_variables = data.shape[3]

    stand_range = np.arange(num_stands)

    assert len(strategies) == num_variables
    assert len(weights) == num_variables

    # initial state
    states = [random.randrange(num_states) for x in range(num_stands)]
    # make sure each stand's state starts with a valid state
    for s, state in enumerate(states):
        if valid_states[s]:
            states[s] = valid_states[s][0]

    cdef float best_metric = float('inf')  
    best_states = states[:]
    best_metrics = []
    cdef float prev_metric = float('inf')
    prev_states = states[:]

    cdef int accepts = 0
    cdef int improves = 0
    cdef int step
    cdef float objective_metric
    cdef float delta
    cdef float rand
    cdef float temp
    cdef float temp_factor = -math.log( temp_max / temp_min )

    #cdef np.ndarray[DTYPE_t, ndim=1] random_comparisons = np.random.uniform(size=steps) 
    #cdef np.ndarray[int, ndim=1] random_stands = np.random.random_integers(0,num_stands-1,size=steps)
    #cdef np.ndarray[int, ndim=1] random_states = np.random.random_integers(0,num_states-1,size=steps)

    cdef np.ndarray[DTYPE_t, ndim=1] property_stddevs
    cdef np.ndarray[DTYPE_t, ndim=2] cumulative_by_time_period
    cdef np.ndarray[DTYPE_t, ndim=3] selected

    theoretical_maxes = [0 for x in range(num_variables)]
    for s, strategy in enumerate(strategies):
        # select the variable, sum to across time periods, take the max for each stand and add them
        theoretical_maxes[s] = data[:,:,:,s].sum(axis=2).max(axis=1).sum()

     

    for step in range(steps):

        # determine temperature
        temp = temp_max * exp(temp_factor * step / steps)

        # pick a random stand and apply a random state to it
        new_stand = random.randrange(num_stands)
        if valid_states[new_stand]:
            # this stand has restricted states, pick from the select list
            new_state = random.choice(valid_states[new_stand])
        else:
            # pick anything
            new_state = random.randrange(num_states)
        states[new_stand] = new_state
        #states[random_stands[step]] = random_states[step]

        # use numpy indexing to select only the desired state of each stand
        # effectively collapses array on states axis to a 3D array (stands x periods x variables)
        selected = data[stand_range, states]

        # calculate the objective metric

        # 2D array
        # stands x sum of each variable over time
        # cumulative_by_stand = selected.sum(axis=1)

        # 2D array
        # time periods x sum of each variable over all stands
        cumulative_by_time_period = selected.sum(axis=0)

        # 1D array
        # useful for cumulative maximize/target
        # property-level cumulative sum of each variable
        property_cumulative = cumulative_by_time_period.sum(axis=0)

        # 1D array
        # useful for evenflow
        # property-level standard deviation of each variable over time
        property_stddevs = cumulative_by_time_period.std(axis=0)

        objective_metrics = []
        for s, strategy in enumerate(strategies):
            if strategy == 'cumulative_maximize':
                # compare the value to the theoretical maximum
                objective_metrics.append((theoretical_maxes[s] - property_cumulative[s]) * weights[s])
            elif strategy == 'evenflow':
                # minimize the standard deviation
                objective_metrics.append(property_stddevs[s] * weights[s])
            elif strategy == 'cumulative_cost':
                # just take cumulative cost
                objective_metrics.append(property_cumulative[s] * weights[s])

        objective_metric = sum(objective_metrics)

        accept = False
        improve = False
        best = False

        delta = objective_metric - prev_metric

        rand = np.random.uniform()
        #rand = random_comparisons[step]
        if delta < 0.0:  # an improvement
            accept = True
            improve = True
        elif exp(-delta/temp) > rand:  # within temperature, accept it
            accept = True
            improve = False

        if step % report_interval == 0:
            print "step: %-7d accepts: %-5d improves: %-5d metric: %-1.2f temp: %-1.2f" % (step, 
                    accepts, improves, prev_metric, temp)
            print "   weighted best: ", zip(variable_names, best_metrics)
            print "        raw best: ", zip(variable_names, [a/b for a,b in zip(best_metrics, weights)])
            print 
            improves = 0
            accepts = 0

        if improve:
            improves += 1

        if accept:
            prev_states = states[:]  # record new state
            prev_metric = objective_metric
            accepts += 1
        else:
            states = prev_states[:]  # restore previous states

        if objective_metric < best_metric:
            best = True
            best_states = states[:]
            best_metric = objective_metric
            best_metrics = objective_metrics

    return best_metric, best_states
