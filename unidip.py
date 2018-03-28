"""
Author: Benjamin Doran
Date: Mar 2018
Algorithm:
    "Skinny-dip: Clustering in a sea of noise" by Samuel Maurus and Claudia Plant.
    http://www.kdd.org/kdd2016/subtopic/view/skinny-dip-clustering-in-a-sea-of-noise
"""

import numpy as np
try:
    from .dip import diptst
except ImportError: # allow tests to run
    from dip import diptst

class UniDip:
    """ Class containing the UniDip clustering algorithm.
        Isolates peaks in high noise samples. 
    """
    def __init__(self, dat, is_hist=False, alpha=0.05, ntrials=100, merge_distance=1, debug=False):
        self.dat = np.msort(np.array(dat)) if not is_hist else np.array(dat)
        self.is_hist = is_hist
        self.alpha = alpha
        self.ntrials = ntrials
        self.merge_distance = merge_distance
        self.debug = debug

    def run(self):
        """ Perform unidip algorithm on 1d array

            INPUT:
            dat: 1d np.array of floats or ints
            offset: int, offset from dat[0]
            is_hist: bool, flips from looking at x axis to density along x axis
            alpha: float, tuning parameter, sets significance level of p_values
            _is_model: internal should not be changed
            numt: int, number of trials in diptest
            plotdat: none or dat, determines whether to plot the data at each recursion level

            RETURNS:
            list of tuples: each tuple containing the start and end indecies on the x axis.
        """
        modidxs = self._unidip(0, len(self.dat), True, self.debug)
        return self.merge_intervals(modidxs)

    def merge_intervals(self, idxs):
        """ merge intervals that are touching """
        midxs = []
        for idx in sorted(idxs):
            if not midxs:
                midxs.append(idx)
            else:
                lower = midxs[-1]
                # adjacent or overlapping (adjust MERGE_DISTANCE to merge intervals)
                # that are close enough
                if idx[0] - lower[1] <= self.merge_distance:
                    midxs[-1] = (lower[0], idx[1])
                else:
                    midxs.append(idx)
        return midxs

    def plot(self, sub, ints, plot_style="seaborn"):
        """ Plot complete data, highlight subset currently being searched,
            and add vertical lines for discovered intervals. (only intervals of
            the current level appear.)
        """
        import matplotlib.pyplot as plt
        plt.style.use(plot_style)
        
        if self.is_hist:
            plt.step(list(range(len(self.dat))), self.dat)
            plt.fill_between(list(range(len(self.dat))), self.dat, step="pre", alpha=.4)
            plt.axvspan(sub[0], sub[1]-1, color="orange", alpha=.3)
            for i in ints:
                plt.axvspan(i[0], i[1], color="green", alpha=.1)
            for i in ints:
                plt.axvline(i[0], color="black")
                plt.axvline(i[1], color="black")
        else:
            dat = np.msort(self.dat)
            plt.hist(dat, bins=30)
            plt.axvspan(dat[sub[0]], dat[sub[1]-1], color="orange", alpha=.3)
            for i in ints:
                plt.axvspan(dat[i[0]], dat[i[1]], color="green", alpha=.1)
            for i in ints:
                plt.axvline(dat[i[0]], color="black")
                plt.axvline(dat[i[1]], color="black")
        plt.show()

    def _unidip(self, start, end, is_model, debug):
        """ Perform unidip algorithm on 1d array

            INPUT:
            dat: 1d np.array of floats or ints
            offset: int, offset from dat[0]
            is_hist: bool, flips from looking at x axis to density along x axis
            alpha: float, tuning parameter, sets significance level of p_values
            _is_model: internal should not be changed
            numt: int, number of trials in diptest
            plotdat: none or dat, determines whether to plot the data at each recursion level

            RETURNS:
            list of tuples: each tuple containing the start and end indecies on the x axis.
        """
        dat = self.dat[start:end]
        interval_idxs = list()
        
        _, pval, modidx = diptst(dat, self.is_hist, self.ntrials)

        if debug: # if plotting -> show intervals
            self.plot((start, end), [(start+modidx[0], start+modidx[1])])

        # not enough data to count it as significant
        if pval is None:
            return []
        # is unimodal, return interval
        elif pval > self.alpha:
            if is_model:
                interval_idxs.append((start, end-1))
            else:
                wideidx = self._get_full_interval((start, end))
                interval_idxs.append((start+wideidx[0], start+wideidx[1]))
            return interval_idxs

        # recurse into model interval
        rmidx = self._unidip(start+modidx[0], start+modidx[1], True, debug)

        # add returned intervals to our collection
        interval_idxs += rmidx
        # undo offset to get correct indices to data in recursion layer
        subd = list(map(lambda t: (t[0]-start, t[1]-(start-1)), interval_idxs))
        # upper and lower bounds
        l_idx = min(subd + [modidx], key=lambda y: y[1])
        h_idx = max(subd + [modidx])

        # recurse low
        pval = diptst(dat[:l_idx[1]], self.is_hist, self.ntrials)[1]
        if not pval is None and pval < self.alpha:
            rlidx = self._unidip(start, start+l_idx[0], False, debug)
            interval_idxs += rlidx

        # recurse high
        pval = diptst(dat[h_idx[0]:], self.is_hist, self.ntrials)[1]
        if not pval is None and pval < self.alpha:
            rhidx = self._unidip(start+h_idx[1], end, False, debug)
            interval_idxs += rhidx

        # return all intervals
        return interval_idxs
            
    def _get_full_interval(self, mod_int):
        """ Expands discovered intervals
            When looking at unimodal data the dip test tends to return a very narrow
            interval, which can lead to conflicts later. This tends to happen after
            recursing left or right.

            Our solution, taken from the original unidip, is to mirror the data such
            that it is bimodal. We are then able to fully capture the mode, and return
            the full mode from the original data.
        """
        dat = self.dat[mod_int[0]:mod_int[1]]
        ldat = self._mirror_data(dat, left=True)
        ldip = diptst(ldat, self.is_hist, self.ntrials)
        rdat = self._mirror_data(dat, left=False)
        rdip = diptst(rdat, self.is_hist, self.ntrials)

        if ldip[0] > rdip[0]:
            full_indxs = self._un_mirror_idxs(ldip[2], len(dat), mod_int, True)
        else:
            full_indxs = self._un_mirror_idxs(rdip[2], len(dat), mod_int, False)
        return tuple(full_indxs)

    def _mirror_data(self, dat, left):
        """ Mirror dataset.
        input: [1, 2, 3] output: [-2, -1, 0, 1, 2]
        """
        wdat = np.array(dat)
        if self.is_hist:
            if left:
                mdat = np.concatenate((np.flip(wdat[1:], -1), wdat))
            else:
                mdat = np.concatenate((wdat[:-1], np.flip(wdat, -1)))
        else:
            if left:
                pivot = np.min(wdat)
                sdat = wdat-pivot
                mdat = np.concatenate((-sdat[sdat > 0], sdat))
                np.sort(mdat)
            else:
                pivot = np.max(wdat)
                sdat = wdat-pivot
                mdat = np.concatenate((sdat, -sdat[sdat < 0]))
                np.sort(mdat)
        return mdat

    def _un_mirror_idxs(self, vals, length, modidxs, left):
        """ wrapper for _un_mirror_idx() """
        if vals[0] < length and vals[1] > length:
            return modidxs

        ori_idxs = np.array([self._un_mirror_idx(i, length, left) for i in vals])
        return ori_idxs if ori_idxs[0] < ori_idxs[1] else np.flip(ori_idxs, -1)
    
    def _un_mirror_idx(self, idx, length, left):
        """ take index from mirrored data and return the appropriate index for
        original data.

        Using indices prevents issues with floating point imprecision.
        """
        if left:
            idxs = idx-length if idx >= length else length-idx
        else:
            idxs = (2 * length)-idx if idx > length else idx
        return idxs

def test(filename, plot=False, **kwargs):
    """ test filename's.csv peakitude :) """
    from time import time

    
    dat = np.genfromtxt(filename, delimiter=",")
    print(f"length of test on {filename}: {len(dat)}")
    
    unidip = UniDip(dat, **kwargs)

    start = time()
    ints = unidip.run()
    end = time()
    
    print(f"# intervals returned: {len(ints)}")
    print("interval idxs:")
    for i in sorted(ints):
        print(i)
    print(f"time taken {end-start:.2f}sec\n")
    
    if plot:
        unidip.plot((0, len(dat)), ints)

if __name__ == "__main__":
    test("./tests/testsmall.csv") # 0 peaks, not enough data
    test("./tests/peak1.csv", plot=False) # 1 peak
    test("./tests/peak2.csv", plot=False, debug=False) # 2 peaks
    test("./tests/peak3.csv", plot=False) # 3 peaks
    test("./tests/large3.csv", plot=False) # 3 peaks
    test("./tests/test10p.csv", plot=False, debug=False) # 10 peaks
    test("./tests/test1or10p.csv", plot=False, alpha=0.3, merge_distance=5) # 10 peaks small gaps
    test("./tests/test0.5sig.csv", plot=False, debug=False, alpha=.05) # 5 peaks
    test("./tests/histnotsig.csv", plot=False, is_hist=True) # 3 peaks, but n of 10, so 1
    test("./tests/hist3p.csv", plot=False, debug=False, is_hist=True) # 3 peaks, n of 60
    test("./tests/negEntIdxErr.csv", is_hist=True, plot=False) # off by one error in diptst / fixed
    test("./tests/negEntMaxRecErr.csv", is_hist=True, plot=False) # 4 peaks
    print("finished testing!")
