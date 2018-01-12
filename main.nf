#!/usr/bin/env nextflow
IMAGE_FOLD = file('../input')
process MeanCalculation {
    clusterOptions "-S /bin/bash"
    input:
    file fold from IMAGE_FOLD
    output:
    file 'mean_file.npy' into MEAN
    script:
    """
    #!/usr/bin/env python
    import numpy as np
    from glob import glob
    from skimage.io import imread

    photos = glob('$fold/*/*.tif')
    n = len(photos)
    res = np.zeros(shape=3, dtype='float')
    for i, img_path in enumerate(photos):
        img = imread(img_path)
        res += np.mean(img, axis=(0, 1))
    res = res / n
    np.save('mean_file.npy', res)
    """
}

ExtractResPY = file("ExtractFromResNet.py")

IMAGES = file(IMAGE_FOLD + '/*/*.tif')

process ExtractFromResNet {
    clusterOptions "-S /bin/bash"
    input:
    file py from ExtractResPY
    file mean_file from MEAN
    file fold from IMAGE_FOLD
    file img from IMAGES
    output:
    file 'ResNet_Feature.csv' into res_net
    script:
    """
    function pyglib {
        /share/apps/glibc-2.20/lib/ld-linux-x86-64.so.2 --library-path /share/apps/glibc-2.20/lib:$LD_LIBRARY_PATH:/usr/lib64/:/usr/local/cuda/lib64/:/cbio/donnees/pnaylor/cuda/lib64:/usr/lib64/nvidia /cbio/donnees/pnaylor/anaconda2/envs/cpu_tf/bin/python \$@
    }
    pyglib $py $fold $img $mean_file
    """
}
process Regroup {
    clusterOptions "-S /bin/bash"
    input:
    file tbls from res_net .toList()
    output:
    file 'ResNet_Feature.csv' into RES
    script:
    """
    #!/usr/bin/env python
    from glob import glob
    import pandas as pd 


    CSV = glob('*.csv')
    tables = []
    for f in CSV:
        t = read_csv(f, index_col=0)
        t.set_index = [f.replace('.csv', '')]
        tables.append(t)
    final_tle = pd.concat(tables, axis=1)
    final_tle.to_csv('ResNet_Feature.csv')


    """
}

N_SPLIT = 5
TREE_SIZE = [10, 100, 200, 500, 1000, 10000]
NUMBER_P = ["auto", "log2"]

process TrainRF {
    clusterOptions "-S /bin/bash"
    input:
    file table from RES
    val n_splits from N_SPLIT
    each n from TREE_SIZE
    each method from NUMBER_P
    output:
    file "score__${n}__${method}.csv" into RF_SCORES
    script:
    """
    #!/usr/bin/env python
    from sklearn.model_selection import StratifiedKFold
    from pandas import read_csv, DataFrame
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score
    from sklearn.metrics import confusion_matrix
    import numpy as np


    table = read_csv('${table}', index_col=0)
    y = table['y']
    X = table.drop('y', axis=1)
    skf = StratifiedKFold(n_splits=${n_splits})
    val_scores = np.zeros(${n_splits})
    cross = 0
    for train_index, test_index in skf.split(X, y):
        X_train, X_test = X.ix[train_index], X.ix[test_index]
        y_train, y_test = y.ix[train_index], y.ix[test_index]
        clf = RandomForestClassifier(n_estimators=${n}, max_features='${method}')
        clf.fit(X_train, y_train)
        print 'Trained model for fold: {}'.format(cross)
        y_pred_test = clf.predict(X_test)
        y_pred_train = clf.predict(X_train)
        print 'Train Accuracy :: ', accuracy_score(y_train, y_pred_train)
        score_test = accuracy_score(y_test, y_pred_test)
        print 'Test Accuracy  :: ', score_test
        print ' Confusion matrix ', confusion_matrix(y_test, y_pred_test)
        val_scores[cross] = score_test
        cross += 1
    DataFrame(val_scores).to_csv('score__${n}__${method}.csv')
    """
}
