import matplotlib
import pandas as pd
import numpy as np
import h5py
from copy import copy
import talib
import matplotlib.pyplot as plt

from .trade import *
from .statistics import *

# format plots
pd.options.display.float_format = '{:0.2f}'.format
#matplotlib.style.use('default')
matplotlib.rcParams['figure.dpi'] = 100
matplotlib.rcParams['savefig.dpi'] = 300
matplotlib.rcParams['figure.figsize'] = [10.0, 4.0]
matplotlib.rcParams['font.sans-serif'] = ['Roboto', 'sans-serif']
matplotlib.rcParams.update({'font.size': 16})