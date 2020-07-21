# AUTOGENERATED! DO NOT EDIT! File to edit: 00_tabular.ipynb (unless otherwise specified).

__all__ = ['FillMissing', 'Categorize', 'Normalize', 'apply_procs', 'TabularDataset', 'tabular_learner']

# Cell
import numpy as np
import onnxruntime as ort

# Cell
def FillMissing(arr, procs):
    "Fills in missing data in `conts` and potentially generates a new categorical column"
    for idx, name in procs['Inputs']['conts'].items():
        if name in procs['FillMissing']['na_dict'].keys():
            nan = np.argwhere(arr[:,idx]!=arr[:,idx])
            arr[:,idx][nan] = procs['FillMissing']['na_dict'][name]
        if procs['FillMissing']['add_col']:
            arr = np.append(arr, np.expand_dims(arr[:,4]==arr[:,4],1), 1)
    return arr

# Cell
def Categorize(arr, procs):
    "Encodes categorical data in `arr` based on `procs`"
    for idx, name in procs['Inputs']['cats'].items():
        arr[:,idx] = [procs['Categorize'][name][i] for i in arr[:,idx]]
    return arr

# Cell
def Normalize(arr, procs):
    "Normalizes continous data in `arr` based on `procs`"
    for idx, name in procs['Inputs']['conts'].items():
        arr[:,idx] = (arr[:,idx]-procs['Normalize'][name]['mean'])/procs['Normalize'][name]['std']
        return arr

# Cell
def apply_procs(arr, procs):
    "Apply test-time pre-processing on `NumPy` array input"
    arr = FillMissing(arr, procs)
    arr = Categorize(arr, procs)
    arr = Normalize(arr, procs)
    return arr

# Cell
class TabularDataset():
    "A tabular `NumPy` dataset based on `procs` with batch size `bs`"
    def __init__(self, arr, procs, bs=64):
        "Stores array, grabs the indicies for `cats` and `conts`, and generates batches"
        self.arr = arr
        self.cat_idxs = procs['Inputs']['cats'].keys()
        self.cont_idxs = procs['Inputs']['conts'].keys()
        self.bs = bs
        self.make_batches()

    def __getitem__(self, x):
        "Grabs one batch of data and converts it to the proper type"
        row = [self.batches[x][:, list(self.cat_idxs)], self.batches[x][:, list(self.cont_idxs)]]
        row[0] = row[0].astype(np.int64)
        row[1] = row[1].astype(np.float32)
        return row

    def make_batches(self):
        "Splits data into equal sized batches, excluding the final partial"
        n_splits = len(self.arr)//self.bs
        last = len(self.arr) - (len(self.arr) - (n_splits * self.bs))
        if len(self.arr) > self.bs:
            arrs = np.split(self.arr[:last], n_splits)
            arrs.append(self.arr[last:])
        else:
            arrs = [self.arr]
        self.batches = arrs

    def __len__(self): return len(self.arr)//self.bs + (0 if len(self.arr)%self.bs==0 else 1)

# Cell
class tabular_learner():
    "A `Learner`-like wrapper for tabular data"
    def __init__(self, fn):
        "Accepts a `fn` pointing to exported `procs` and ONNX filename"
        self.ort_session = ort.InferenceSession(fn+'.onnx')
        try:
            self.ort_session.set_providers(['CUDAExecutionProvider'])
            cpu = False
        except:
            self.ort_session.set_providers(['CPUExecutionProvider'])
            cpu = True
        with open(f'{fn}.pkl', 'rb') as handle:
            self.procs = pickle.load(handle)
            for proc in self.procs['Categorize']:
                self.procs['Categorize'][proc][np.nan] = 0 # we can't pickle np.nan

    def test_dl(self, test_items, bs=64):
        "Applies `procs` to `test_items`"
        dl = apply_procs(test_items, self.procs)
        return TabularDataset(dl, self.procs, bs=bs)

    def predict(self, inps):
        "Predict a single numpy item"
        names = [i.name for i in self.ort_session.get_inputs()]
        xs = {name:x for name,x in zip(names,inps)}
        outs = self.ort_session.run(None, xs)
        outs = np.argmax(outs[0], axis=1)
        outs = [learn.procs['Outputs'][i] for i in outs]
        return outs

    def get_preds(self, dl=None):
        "Predict on multiple batches of data in `dl`"
        outs = []
        for i, batch in enumerate(dl):
            outs += self.predict(batch)
        return outs