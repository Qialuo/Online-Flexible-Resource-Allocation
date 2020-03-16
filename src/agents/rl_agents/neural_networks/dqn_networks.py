"""
DQN Networks
"""

from __future__ import annotations

import gin.tf
import tensorflow as tf

from agents.rl_agents.neural_networks.network import Network


@gin.configurable
class DqnBidirectionalLstmNetwork(Network):
    """
    DQN Bidirectional Lstm Network
    """

    def __init__(self, input_width: int, action_width: int, lstm_width: int = 40, relu_width: int = 20):
        Network.__init__(self, 'Bidirectional Lstm', input_width, action_width)

        self.bidirectional_lstm = tf.keras.layers.Bidirectional(
            tf.keras.layers.LSTM(lstm_width, input_shape=(None, input_width)))
        self.relu = tf.keras.layers.ReLU(relu_width)
        self.q_value_layer = tf.keras.layers.Dense(action_width)

    def call(self, inputs, training=None, mask=None):
        """
        Forward propagation through the neural network

        Args:
            inputs: numpy ndarray input observation for the network
            training: Ignored
            mask: Ignored

        Returns: Single dimensional array action output

        """
        return self.q_value_layer(self.relu(self.bidirectional_lstm(inputs)))


@gin.configurable
class DqnLstmNetwork(Network):
    """
    DQN Lstm Network
    """

    def __init__(self, input_width: int, action_width: int, lstm_width: int = 40, relu_width: int = 20):
        Network.__init__(self, 'Lstm', input_width, action_width)

        self.lstm = tf.keras.layers.LSTM(lstm_width, input_shape=(None, input_width))
        self.relu = tf.keras.layers.ReLU(relu_width)
        self.q_value_layer = tf.keras.layers.Dense(action_width)

    def call(self, inputs, training=None, mask=None):
        """
        Forward propagation through the neural network

        Args:
            inputs: numpy ndarray input observation for the network
            training: Ignored
            mask: Ignored

        Returns: Single dimensional array action output

        """
        return self.q_value_layer(self.relu(self.lstm(inputs)))


@gin.configurable
class DqnGruNetwork(Network):
    """
    DQN Gru Network
    """

    def __init__(self, input_width: int, action_width: int, lstm_width: int = 40, relu_width: int = 20):
        Network.__init__(self, 'Gru', input_width, action_width)

        self.gru = tf.keras.layers.GRU(lstm_width, input_shape=(None, input_width))
        self.relu = tf.keras.layers.ReLU(relu_width)
        self.q_value_layer = tf.keras.layers.Dense(action_width)

    def call(self, inputs, training=None, mask=None):
        """
        Forward propagation through the neural network

        Args:
            inputs: numpy ndarray input observation for the network
            training: Ignored
            mask: Ignored

        Returns: Single dimensional array action output

        """
        return self.q_value_layer(self.relu(self.gru(inputs)))