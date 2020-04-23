"""
Tests that agent implementations; constructor attributes, agent saving, task pricing / resource allocation training
"""

from __future__ import annotations

import tensorflow as tf

from agents.rl_agents.agents.c51 import TaskPricingCategoricalDqnAgent, ResourceWeightingCategoricalDqnAgent
from agents.rl_agents.agents.ddpg import TaskPricingDdpgAgent, ResourceWeightingDdpgAgent, TaskPricingTD3Agent, \
    ResourceWeightingTD3Agent
from agents.rl_agents.agents.dqn import TaskPricingDqnAgent, TaskPricingDdqnAgent, TaskPricingDuelingDqnAgent, \
    ResourceWeightingDqnAgent, ResourceWeightingDdqnAgent, ResourceWeightingDuelingDqnAgent
from agents.rl_agents.neural_networks.ddpg_networks import create_lstm_critic_network, create_lstm_actor_network
from agents.rl_agents.neural_networks.dqn_networks import create_lstm_dueling_dqn_network, create_lstm_dqn_network, \
    create_lstm_categorical_dqn_network
from env.environment import OnlineFlexibleResourceAllocationEnv

# TODO add comments and new agents


def test_build_agent():
    def assert_args(test_agent, args):
        """
        Asserts that the proposed arguments have assigned to the agent

        Args:
            test_agent: The test agent
            args: The argument used on the agent
        """
        for arg_name, arg_value in args.items():
            assert getattr(test_agent, arg_name) == arg_value, \
                f'Attr: {arg_name}, correct value: {arg_value}, actual value: {getattr(test_agent, arg_name)}'

    # Check inheritance arguments
    reinforcement_learning_arguments = {
        'batch_size': 16, 'error_loss_fn': tf.compat.v1.losses.mean_squared_error, 'initial_training_replay_size': 1000,
        'update_frequency': 2, 'replay_buffer_length': 20000, 'save_frequency': 12500, 'save_folder': 'test',
        'discount_factor': 0.9
    }
    dqn_arguments = {
        'target_update_tau': 1.0, 'target_update_frequency': 2500, 'optimiser': tf.keras.optimizers.Adadelta(),
        'initial_epsilon': 0.5, 'final_epsilon': 0.2, 'epsilon_update_frequency': 25
    }
    ddpg_arguments = {
        'actor_optimiser': tf.keras.optimizers.Adadelta(), 'critic_optimiser': tf.keras.optimizers.Adadelta(),
        'initial_epsilon_std': 0.8, 'final_epsilon_std': 0.1, 'epsilon_update_frequency': 25, 'min_value': -15.0,
        'max_value': 15
    }
    pricing_arguments = {'failed_auction_reward': -100, 'failed_multiplier': -100}
    weighting_arguments = {'other_task_discount': 0.2, 'success_reward': 1, 'failed_reward': -2}

    # DQN Agent arguments ----------------------------------------------------------------------
    dqn_pricing_arguments = {**reinforcement_learning_arguments, **dqn_arguments, **pricing_arguments}
    dqn_weighting_arguments = {**reinforcement_learning_arguments, **dqn_arguments, **weighting_arguments}

    pricing_network = create_lstm_dqn_network(9, 10)
    pricing_agents = [
        TaskPricingDqnAgent(0, pricing_network, **dqn_pricing_arguments),
        TaskPricingDdqnAgent(1, pricing_network, **dqn_pricing_arguments),
        TaskPricingDuelingDqnAgent(2, pricing_network, **dqn_pricing_arguments)
    ]
    for agent in pricing_agents:
        assert_args(agent, dqn_pricing_arguments)

    weighting_network = create_lstm_dqn_network(16, 10)
    weighting_agents = [
        ResourceWeightingDqnAgent(0, weighting_network, **dqn_weighting_arguments),
        ResourceWeightingDdqnAgent(1, weighting_network, **dqn_weighting_arguments),
        ResourceWeightingDuelingDqnAgent(2, weighting_network, **dqn_weighting_arguments)
    ]
    for agent in weighting_agents:
        assert_args(agent, dqn_weighting_arguments)

    # PG Agent arguments ----------------------------------------------------------------------------------
    ddpg_pricing_arguments = {**reinforcement_learning_arguments, **ddpg_arguments, **pricing_arguments}
    ddpg_weighting_arguments = {**reinforcement_learning_arguments, **ddpg_arguments, **weighting_arguments}

    pricing_agents = [
        TaskPricingDdpgAgent(3, create_lstm_actor_network(9), create_lstm_critic_network(9), **ddpg_pricing_arguments),
        TaskPricingTD3Agent(4, create_lstm_actor_network(9), create_lstm_critic_network(9),
                            create_lstm_critic_network(9), **ddpg_pricing_arguments)
    ]
    for pricing_agent in pricing_agents:
        assert_args(pricing_agent, ddpg_pricing_arguments)

    weighting_agents = [
        ResourceWeightingDdpgAgent(3, create_lstm_actor_network(16), create_lstm_critic_network(16),
                                   **ddpg_weighting_arguments),
        ResourceWeightingTD3Agent(4, create_lstm_actor_network(16), create_lstm_critic_network(16),
                                  create_lstm_critic_network(16), **ddpg_weighting_arguments)
    ]
    for weighting_agent in weighting_agents:
        assert_args(weighting_agent, ddpg_weighting_arguments)


def test_saving_agent():
    print()
    # Different agents
    dqn_agent = TaskPricingDqnAgent(0, create_lstm_dqn_network(9, 10), save_folder='tmp')
    ddpg_agent = TaskPricingDdpgAgent(1, create_lstm_actor_network(9), create_lstm_critic_network(9), save_folder='tmp')
    td3_agent = TaskPricingTD3Agent(2, create_lstm_actor_network(9), create_lstm_critic_network(9),
                                    create_lstm_critic_network(9), save_folder='tmp')

    # Save the agent
    dqn_agent.save('agent/checkpoints/')
    ddpg_agent.save('agent/checkpoints/')
    td3_agent.save('agent/checkpoints/')

    # Check that loading works
    loaded_model = create_lstm_dqn_network(9, 10)
    loaded_model.load_weights(f'agent/checkpoints/tmp/Task_pricing_Dqn_agent_0')

    assert all(tf.reduce_all(weights == load_weights)
               for weights, load_weights in zip(dqn_agent.model_network.variables, loaded_model.variables))


def test_agent_actions():
    print()
    pricing_agents = [
        TaskPricingDqnAgent(0, create_lstm_dqn_network(9, 5)),
        TaskPricingDdqnAgent(1, create_lstm_dqn_network(9, 5)),
        TaskPricingDuelingDqnAgent(2, create_lstm_dueling_dqn_network(9, 5)),
        TaskPricingCategoricalDqnAgent(5, create_lstm_categorical_dqn_network(9, 5)),
        TaskPricingDdpgAgent(3, create_lstm_actor_network(9), create_lstm_critic_network(9)),
        TaskPricingTD3Agent(4, create_lstm_actor_network(9), create_lstm_critic_network(9),
                            create_lstm_critic_network(9))
    ]
    weighting_agents = [
        ResourceWeightingDqnAgent(0, create_lstm_dqn_network(16, 5)),
        ResourceWeightingDdqnAgent(1, create_lstm_dqn_network(16, 5)),
        ResourceWeightingDuelingDqnAgent(2, create_lstm_dueling_dqn_network(16, 5)),
        ResourceWeightingCategoricalDqnAgent(5, create_lstm_categorical_dqn_network(16, 5)),
        ResourceWeightingDdpgAgent(3, create_lstm_actor_network(16), create_lstm_critic_network(16)),
        ResourceWeightingTD3Agent(4, create_lstm_actor_network(16), create_lstm_critic_network(16),
                                  create_lstm_critic_network(16))
    ]

    env, state = OnlineFlexibleResourceAllocationEnv.load_env('agent/settings/actions.env')
    actions = {
        server: pricing_agents[pos].bid(state.auction_task, tasks, server, state.time_step)
        for pos, (server, tasks) in enumerate(state.server_tasks.items())
    }
    print(f'Actions: {{{", ".join([f"{server.name}: {action}" for server, action in actions.items()])}}}')

    state, rewards, done, _ = env.step(actions)

    actions = {
        server: weighting_agents[pos].weight(tasks, server, state.time_step)
        for pos, (server, tasks) in enumerate(state.server_tasks.items())
    }
    print(f'Actions: {{{", ".join([f"{server.name}: {list(task_action.values())}" for server, task_action in actions.items()])}}}')
    assert any(0 < action for server, task_actions in actions.items() for task, action in task_actions.items())

    state, rewards, done, _ = env.step(actions)
