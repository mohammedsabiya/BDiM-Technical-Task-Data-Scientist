# -*- coding: utf-8 -*-
"""Sabiya_technical_task_good.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1uvCD6XVx2n3_otodub7-62VgZvkd1OB_
"""

# import the necessary libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
import random
from statsmodels.tsa.stattools import acf
from imblearn.over_sampling import SMOTE
from imblearn.combine import SMOTETomek
from imblearn.under_sampling import TomekLinks
from collections import Counter
import tensorflow as tf
from scipy.fft import fft
from scipy.signal import get_window
from tensorflow.keras.optimizers import Adam
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score
from tensorflow.keras.models import Sequential
from sklearn.utils.class_weight import compute_class_weight
from tensorflow.keras.layers import Conv1D, MaxPooling1D, LSTM, Dense, Dropout, BatchNormalization, Reshape
from tensorflow.keras.regularizers import l2
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from sklearn.model_selection import TimeSeriesSplit

import optuna
import warnings
warnings.filterwarnings('ignore')

# fetch "healthy data" and "anomalies" datasets and read them
healthy_data = pd.read_hdf("/content/drive/MyDrive/dataset/healthy_data.h5")
anomalies = pd.read_hdf("/content/drive/MyDrive/dataset/anomalies.h5")

# create a new column "label"
# label the "healthy data" data as "0" for normal and "anomalies" data as "1" for abnormal
healthy_data['label'] = 0
anomalies['label'] = 1

# combine both "healthy data" and "anomalies" datasets into one dataframe
data = pd.concat([healthy_data, anomalies], axis=0).reset_index(drop=True)


# randomly shuffle the rows to have a mixed rows of "healthy data" and "anomalies" sampl
data_shuffled = data.sample(frac=1, random_state=42).reset_index(drop=True)

# check the shuffled DataFrame
print(data_shuffled.head())

# checking the labels count for imbalance
# observation: there is a class imbalance
data_shuffled.label.value_counts()

# descriptive analysis
data_shuffled.describe()

# check for NaN or Null values
data_shuffled.loc[data_shuffled.isnull().any(axis=1), data_shuffled.isnull().any()]

labels = data_shuffled["label"].values  # Extract labels
features = data_shuffled.drop(columns=["label"])  # Drop the label column from data to have features

# distribution analysis
# histogram of features df to visualize the distribution
plt.figure(figsize=(12, 6))
sns.histplot(features.iloc[:, 200], kde=True)
plt.title('Histogram and KDE of Feature')
plt.xlabel('Feature Value')
plt.ylabel('Frequency')
plt.show()

# autocorrelation analysis

# Number of lags to analyze
lags = 50

# select a few sequences randomly
sequences_to_analyze = random.sample(range(features.shape[0]), 5)


# plot the autocorrelation for selected sequences
plt.figure(figsize=(12, 8))

for idx in sequences_to_analyze:
    sequence_data = features.iloc[idx]  # get the samples (row) at index `idx`

    # compute autocorrelation for the sample
    autocorr_values = acf(sequence_data, nlags=lags)

    # plot the autocorrelation values
    plt.plot(range(lags + 1), autocorr_values, label=f'Sample {idx}')

# plot customization
plt.title('Autocorrelation of Selected Samples')
plt.xlabel('Lag')
plt.ylabel('Autocorrelation')
plt.legend()
plt.grid(True)
plt.show()

# Implement a random seed to have random reproducibility
random.seed(42)
np.random.seed(42)
tf.random.set_seed(42)

# split the dataset into train set, valid set, and test set
X_train, X_temp, y_train, y_temp = train_test_split(features, labels, test_size=0.4, random_state=42, stratify=labels)
X_valid, X_test, y_valid, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp)

print("Training data shape:", X_train.shape)
print("Validation data shape:", X_valid.shape)
print("Testing data shape:", X_test.shape)

# oversample the train set to address the class imbalance problem.
# only train set is resampled for balancing the class in order to keep the valid set as the same because this allows to test the model on real-world scenerio.
smote = SMOTE(random_state=42)
X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

# normalize the train set to standardize the feature values in the range [0,1].
scaler = StandardScaler()
X_train_normalized = scaler.fit_transform(X_train_resampled)

# normalize both valid and test set.
X_valid_normalized = scaler.transform(X_valid)
X_test_normalized = scaler.transform(X_test)

# perform Fast Fourier transformation (fft) to the data using sliding windows with windowing functions.
def fft_transformation_sliding_window(data, window_size, overlap, sampling_rate):
    """
    Parameters:
    - data: 2D numpy array of shape (num_sequences, num_samples)
      This is the input data, where each row represents a time-series signal for one sequence.
    - window_size: int, the size of the sliding window
      Defines the number of samples in each window for FFT computation, impacting frequency resolution.
    - overlap: int, the number of overlapping samples
      Determines how much overlap exists between consecutive windows. Higher overlap provides finer temporal resolution.
    - sampling_rate: int, the sampling rate in Hz
      Represents the frequency at which the acceleration data was sampled, which is required to interpret the FFT results.

    Returns:
    - fft_results: 3D numpy array of shape (num_sequences, num_windows, num_frequency_bins)
      FFT magnitudes computed for each window in each sequence, where `num_windows` is the number of windows derived from `window_size` and `overlap`.
    - freqs: 1D numpy array of frequency bins
      Array of frequency values corresponding to the FFT output, in Hz.

    """
    step = window_size - overlap
    num_windows = (data.shape[1] - window_size) // step + 1

    # prepare to store FFT results
    fft_results = []

    for sequence in data:
        sequence_fft = []
        for start in range(0, len(sequence) - window_size + 1, step):
            window = sequence[start:start + window_size]
            windowed_signal = window * get_window('hann', window_size)  # perform a Hann window
            fft_values = np.fft.rfft(windowed_signal)  # compute FFT
            fft_magnitude = np.abs(fft_values)  # get magnitude
            sequence_fft.append(fft_magnitude)

        fft_results.append(sequence_fft)

    # convert the results to a numpy array
    fft_results = np.array(fft_results)

    # Cclculate frequency bins
    num_frequency_bins = fft_results.shape[2]
    freqs = np.fft.rfftfreq(window_size, d=1/sampling_rate)

    return fft_results, freqs

sampling_rate = 1024  # Hz
window_size = 1024    # size of the window
overlap = 512         # overlap between windows

# perform FFT on the normalized datasets with sliding windows
X_train_fft, train_freqs = fft_transformation_sliding_window(X_train_normalized, window_size, overlap, sampling_rate)
X_valid_fft, valid_freqs = fft_transformation_sliding_window(X_valid_normalized, window_size, overlap, sampling_rate)
X_test_fft, test_freqs = fft_transformation_sliding_window(X_test_normalized, window_size, overlap, sampling_rate)

print("Training FFT data shape:", X_train_fft.shape)
print("Validation FFT data shape:", X_valid_fft.shape)
print("Testing FFT data shape:", X_test_fft.shape)

# calculate class weights to handle class imbalance
class_weights = compute_class_weight(class_weight='balanced', classes=np.unique(y_train_resampled), y=y_train_resampled)
class_weights_dict = dict(enumerate(class_weights))

# create a model with CNN+LSTM architecture to
def create_cnn_lstm_model(conv_filters, kernel_size, num_units_1, dense_units_1, dropout_rate, input_shape, l2_reg, learning_rate):
   """
    Create a CNN-LSTM model for sequence data classification.

    Parameters:
    - conv_filters (int): Number of filters in the convolutional layers.
    - kernel_size (int): Size of the convolutional kernel.
    - num_units_1 (int): Number of units in the LSTM layer.
    - dense_units_1 (int): Number of units in the dense layer after LSTM.
    - dropout_rate (float): Dropout rate to prevent overfitting.
    - input_shape (tuple): Shape of the input data (sequence length, number of features).
    - l2_reg (float): L2 regularization factor to reduce model complexity.
    - learning_rate (float): Learning rate for the Adam optimizer.

    Returns:
    - model (Sequential): Compiled CNN-LSTM model.
    """

    model = Sequential()

    # 1D convolutional layer
    model.add(Conv1D(filters=conv_filters, kernel_size=kernel_size, activation='relu', input_shape=input_shape))
    model.add(BatchNormalization())
    model.add(MaxPooling1D(pool_size=2))
    model.add(Dropout(dropout_rate))

    # second Conv1D layer for deeper feature extraction
    model.add(Conv1D(filters=conv_filters * 2, kernel_size=kernel_size, activation='relu'))
    model.add(BatchNormalization())
    model.add(MaxPooling1D(pool_size=2))
    model.add(Dropout(dropout_rate))

    # LSTM layer
    model.add(LSTM(num_units_1, kernel_regularizer=l2(l2_reg)))
    model.add(BatchNormalization())
    model.add(Dropout(dropout_rate))

    model.add(Dense(dense_units_1, activation='relu', kernel_regularizer='l2'))
    model.add(BatchNormalization())
    model.add(Dropout(dropout_rate))

    model.add(Dense(1, activation='sigmoid'))

    # optimize the learning rate
    optimizer = Adam(learning_rate=learning_rate)

    model.compile(optimizer=optimizer, loss='binary_crossentropy', metrics=['accuracy'])

    return model

def objective(trial):

    """
    Objective function for Optuna hyperparameter optimization.

    This function defines the model's architecture and training parameters for
    a CNN-LSTM binary classification task. Using Optuna, it samples hyperparameters
    from specified ranges and evaluates model performance on a validation set.

    Parameters:
    - trial: An Optuna trial object, which suggests values for each hyperparameter
      within specified ranges.

    Hyperparameters Sampled:
    - conv_filters (int): Number of convolutional filters in the 1D convolution layers,
      sampled from the range [32, 128] in steps of 16.
    - kernel_size (int): Size of the convolution kernel, sampled from [1, min(X_train.shape[1], 5)].
    - dense_units_1 (int): Number of units in the first dense layer, sampled from [32, 64] in steps of 16.
    - num_units_1 (int): Number of units in the LSTM layer, sampled from [16, 64] in steps of 16.
    - dropout_rate (float): Dropout rate for regularization, sampled from a range between 0.3 and 0.5.
    - l2_reg (float): L2 regularization factor, sampled logarithmically from [1e-6, 1e-2].
    - learning_rate (float): Learning rate for the Adam optimizer, sampled logarithmically
      from [1e-5, 1e-2].

    Training Configuration:
    - Early stopping is used to prevent overfitting, with `patience` set to 10 and
      `restore_best_weights` enabled.
    - The model is trained for a maximum of 100 epochs with a batch size of 64.
    - Class weights (computed externally) are used to handle class imbalance.

    Returns:
    - f1 (float): The F1 score calculated on the validation set, which is used
      by Optuna to determine the best hyperparameter configuration.

    """

    # hyperparameters
    conv_filters = trial.suggest_int('conv_filters', 32, 128, step=16)
    kernel_size = trial.suggest_int('kernel_size', 1, min(X_train.shape[1], 5))
    dense_units_1 = trial.suggest_int('dense_units_1', 32, 64, step=16)
    num_units_1 = trial.suggest_int('num_units_1', 16, 64, step=16)
    dropout_rate = trial.suggest_float('dropout_rate', 0.3, 0.5)
    l2_reg = trial.suggest_loguniform('l2_reg', 1e-6, 1e-2)
    learning_rate = trial.suggest_loguniform('learning_rate', 1e-5, 1e-2)

    early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)

    # Create the model
    input_shape = (X_train_fft.shape[1], X_train_fft.shape[2])
    model = create_cnn_lstm_model(conv_filters, kernel_size, num_units_1, dense_units_1, dropout_rate, input_shape, l2_reg, learning_rate)

    # Fit the model
    history = model.fit(X_train_fft, y_train_resampled,
                        validation_data=(X_valid_fft, y_valid),
                        epochs=100,
                        batch_size=64,
                        class_weight=class_weights_dict,
                        verbose=0,
                        callbacks=[early_stopping])

    predict = model.predict(X_valid_fft)

    # Calculate the f1-score
    f1 = f1_score(y_valid, np.round(predict))

    # Return the f1-score
    return f1

# Step 1: Create a study object
study = optuna.create_study(direction='maximize')
# Step 2: Optimize hyperparameters
study.optimize(objective, n_trials=30)

# Output the best hyperparameters
print("Best hyperparameters: ", study.best_params)
print("Best validation f1-score: ", study.best_value)

import json

# get the best trial from the optuna study
best_trial = study.best_trial

# extract the best hyperparameters and best f1-score (value)
best_params = best_trial.params
best_value = best_trial.value

# save the best parameters and value to a JSON file
with open('best_trial_params.json', 'w') as f:
    json.dump({
        'best_params': best_params,
        'best_value': best_value
    }, f)

print("Best Trial Parameters:")
print(best_params)
print("Best Trial Value (F1 Score):", best_value)

# add the "input_shape" to the best_params dictionary as it is one of the inputsput for the model
best_params['input_shape'] = (X_train_fft.shape[1], X_train_fft.shape[2])

# refit the model with the best parameters obtained from the optuna study with the same model architecture
model = create_cnn_lstm_model(**best_params)

early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)

history = model.fit(X_train_fft, y_train_resampled,
          validation_data=(X_valid_fft, y_valid),
          epochs=100,
          batch_size=64,
          class_weight=class_weights_dict,
          verbose=0,
          callbacks=[early_stopping])

# evluate the model performance on the validation set
valid_predict = model.predict(X_valid_fft) # make predictions on the validation set using the trained model

# calculate the f1-score of the validation set
f1 = f1_score(y_valid, np.round(valid_predict))
print("Validation F1-Score: ", f1)

# evaluate the model using loss and accuracy metrics on the validation set
loss, accuracy = model.evaluate(X_valid_fft, y_valid)

# visualize the training and validation loss over epochs to ensure the trained model is not overfitting
plt.plot(history.history['loss'], label='Train Loss')
plt.plot(history.history['val_loss'], label='Validation Loss')
plt.title('Model Loss')
plt.ylabel('Loss')
plt.xlabel('Epoch')
plt.legend()
plt.show()

# save the trained model
model.save("good_result_cnn_lstm_model.h5")

# lastly, evaluate the trained model on the test set
test_predict = model.predict(X_test_fft) # make prediction on the test set
test_f1 = f1_score(y_test, np.round(test_predict)) # compute the f1-score
print("Test F1-Score: ", test_f1)

# get predictions from the model
test_pred_acc = model.predict(X_test_fft)

# convert probabilities to binary predictions
test_pred_classes = (test_pred_acc > 0.5).astype("int32")

# calculate the accuracy of the test set
accuracy = accuracy_score(y_test, test_pred_classes)
print(f"Test Accuracy: {accuracy}")

# compute the confusion matrix on the test set
cm = confusion_matrix(y_test, np.round(test_pred_acc))
print("Confusion Matrix:\n", cm)

# visualize the confusion matrix
ax= plt.subplot()
#fig, ax = plt.subplots(figsize=(8,5))
sns.set(font_scale=1.5)
sns.heatmap(cm, annot = True, fmt ='g', ax = ax, cmap = sns.cubehelix_palette(as_cmap=True));

ax.set_xlabel('Predicted labels');ax.set_ylabel('True labels');
ax.set_title('Confusion Matrix');