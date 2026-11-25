"""Run in an environment where the notebook model was saved as .keras.

Alternative: paste the np.savez_compressed block into the notebook after training.
No TensorFlow/Keras is needed on the offline recognition PC.
"""
import argparse
import numpy as np

def export(model,path):
    arrays=model.get_weights()
    if len(arrays)!=6:raise ValueError('Expected three Dense layers, six weight arrays')
    np.savez_compressed(path,**dict(zip(['w1','b1','w2','b2','w3','b3'],arrays)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('keras_model');parser.add_argument('output_npz');args=parser.parse_args()
    import keras
    export(keras.models.load_model(args.keras_model,compile=False),args.output_npz)
