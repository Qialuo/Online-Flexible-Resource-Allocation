"""
Core functions in training of agents
"""

from __future__ import annotations

import datetime as dt
import os
import random as rnd
from typing import List, Dict, Tuple, Optional, TYPE_CHECKING

import tensorflow as tf
from tensorflow.python.ops.summary_ops_v2 import ResourceSummaryWriter

from env.env_state import EnvState
from env.environment import OnlineFlexibleResourceAllocationEnv
from env.task_stage import TaskStage

if TYPE_CHECKING:
    from env.server import Server
    from agents.task_pricing_agent import TaskPricingAgent
    from agents.resource_weighting_agent import ResourceWeightingAgent
    from agents.rl_agents.rl_agents import TaskPricingRLAgent, ResourceWeightingRLAgent, TaskPricingState, \
        ResourceAllocationState


def allocate_agents(state: EnvState, task_pricing_agents: List[TaskPricingAgent],
                    resource_weighting_agents: List[ResourceWeightingAgent]) \
        -> Tuple[Dict[Server, TaskPricingAgent], Dict[Server, ResourceWeightingAgent]]:
    """
    Allocates agents to servers

    Args:
        state: Environment state with a list of servers
        task_pricing_agents: List of task pricing agents
        resource_weighting_agents: List of resource weighting agents

    Returns: A tuple of dictionaries, one for the server, task pricing agents and
        the other, server, resource weighting agents
    """
    server_task_pricing_agents = {
        server: rnd.choice(task_pricing_agents) for server in state.server_tasks.keys()
    }
    server_resource_weighting_agents = {
        server: rnd.choice(resource_weighting_agents) for server in state.server_tasks.keys()
    }

    return server_task_pricing_agents, server_resource_weighting_agents


def eval_agent(env_filenames: List[str], episode: int, pricing_agents: List[TaskPricingAgent],
               weighting_agents: List[ResourceWeightingAgent]):
    """
    Evaluation of agents using a list of preset environments

    Args:
        env_filenames: Evaluation environment filenames
        episode: The episode of evaluation
        pricing_agents: List of task pricing agents
        weighting_agents: List of resource weighting agents
    """
    total_task_prices, completed_tasks, failed_tasks = 0, 0, 0
    for env_filename in env_filenames:
        eval_env, state = OnlineFlexibleResourceAllocationEnv.load_env(env_filename)
        server_pricing_agents, server_weighting_agents = allocate_agents(state, pricing_agents, weighting_agents)

        done = False
        while not done:
            if state.auction_task:
                bidding_actions = {
                    server: server_pricing_agents[server].bid(state.auction_task, tasks, server, state.time_step)
                    for server, tasks in state.server_tasks.items()
                }
                state, rewards, done, info = eval_env.step(bidding_actions)
            else:
                weighting_actions = {
                    server: server_weighting_agents[server].weight(tasks, server, state.time_step)
                    for server, tasks in state.server_tasks.items()
                }
                state, rewards, done, info = eval_env.step(weighting_actions)
                for finished_tasks in rewards.values():
                    for finished_task in finished_tasks:
                        total_task_prices += finished_task.price * (1 if finished_task.stage is TaskStage.COMPLETED else -1)
                        if finished_task.stage is TaskStage.COMPLETED:
                            completed_tasks += 1
                        elif finished_task.stage is TaskStage.FAILED:
                            failed_tasks += 1
                        else:
                            raise Exception(f'Unexpected task stage: {finished_task.stage}, {str(finished_task)}')

    print(f'Eval episode {episode} - total price: {total_task_prices}, '
          f'completed tasks: {completed_tasks}, failed tasks: {failed_tasks}')
    tf.summary.scalar('Eval total price', total_task_prices, step=episode)
    tf.summary.scalar('Eval total completed tasks', completed_tasks, step=episode)
    tf.summary.scalar('Eval total failed tasks', failed_tasks, step=episode)


def train_agent(training_env: OnlineFlexibleResourceAllocationEnv, pricing_agents: List[TaskPricingRLAgent],
                weighting_agents: List[ResourceWeightingRLAgent]):
    """
    Trains reinforcement learning agents through the provided environment

    Args:
        training_env: Training environment used
        pricing_agents: A list of reinforcement learning task pricing agents
        weighting_agents: A list of reinforcement learning resource weighting agents
    """
    # Reset the environment getting a new training environment for this episode
    state = training_env.reset()

    # Allocate the servers with their random task pricing and resource weighting agents
    server_pricing_agents: Dict[Server, TaskPricingRLAgent] = {
        server: rnd.choice(pricing_agents) for server in state.server_tasks.keys()
    }
    server_weighting_agents: Dict[Server, ResourceWeightingRLAgent] = {
        server: rnd.choice(weighting_agents) for server in state.server_tasks.keys()
    }

    # Store each server's auction observations with it being (None for first auction because no observation was seen previously)
    #   the agent state for the auction (auction task, server tasks, server, time), the action taken and if the auction task was won
    server_auction_agent_states: Dict[Server, Optional[Tuple[TaskPricingState, float, bool]]] = {
        server: None for server in state.server_tasks.keys()
    }

    # For successful auctions, then the agent state of the winning bid, the action taken and the following observation are
    #   all stored in order to be added as an agent observation after the task finishes in order to know if the task was completed or not
    successful_auction_agent_states: List[Tuple[TaskPricingState, float, TaskPricingState]] = []

    # The environment is looped over till the environment is done (the current time step > environment total time steps)
    done = False
    while not done:
        # If the state has a task to be auctioned then find the pricing of each servers as the action
        if state.auction_task:
            # Get the bids for each server
            auction_prices = {
                server: server_pricing_agents[server].bid(state.auction_task, tasks, server, state.time_step)
                for server, tasks in state.server_tasks.items()
            }

            # Environment step using the pricing actions to get the next state, rewards, done and info
            next_state, rewards, done, info = training_env.step(auction_prices)

            # Update the server_auction_observations and auction_trajectories variables with the new next_state info
            for server, tasks in state.server_tasks.items():
                # Generate the current agent's state
                current_state = TaskPricingState(state.auction_task, tasks, server, state.time_step)

                if server_auction_agent_states[server]:  # If a server auction observation exists
                    # Get the last time steps agent state, action and if the server won the auction
                    previous_state, previous_action, previous_auction_win = server_auction_agent_states[server]

                    # If the server won the auction in the last time step then add the info to the auction trajectories
                    if previous_auction_win:
                        successful_auction_agent_states.append((previous_state, previous_action, current_state))
                    else:
                        # Else add the agent state to the agent's replay buffer as a failed auction bid
                        # Else add the observation as a failure to the task pricing rl_agents
                        server_pricing_agents[server].failed_auction_bid(previous_state, previous_action, current_state)

                # Update the server auction agent states with the current agent state
                server_auction_agent_states[server] = (current_state, auction_prices[server], server in rewards)
        else:  # Else the environment is at resource allocation stage
            # For each server and each server task calculate its relative weighting
            weighting_actions = {
                server: server_weighting_agents[server].weight(tasks, server, state.time_step)
                for server, tasks in state.server_tasks.items()
            }

            # Environment step using the resource weighting actions to get the next state, rewards, done and info
            next_state, finished_server_tasks, done, info = training_env.step(weighting_actions)

            # For each server, there are may be finished tasks due to the resource allocation
            #    therefore add the task pricing auction agent states with the finished tasks
            for server, finished_tasks in finished_server_tasks.items():
                for finished_task in finished_tasks:
                    # Get the successful auction agent state from the list of successful auction agent states
                    successful_auction = next(auction_agent_state
                                              for auction_agent_state in successful_auction_agent_states
                                              if auction_agent_state[0].auction_task == finished_task)
                    # Remove the successful auction agent state
                    successful_auction_agent_states.remove(successful_auction)

                    # Unwrap the successful auction agent state tuple
                    auction_state, action, next_state = successful_auction

                    # Add the winning auction bid info to the agent
                    server_pricing_agents[server].winning_auction_bid(auction_state, action, finished_task, next_state)

            # Add the agent states for resource allocation
            for server, tasks in state.server_tasks.items():
                agent_state = ResourceAllocationState(tasks, server, state.time_step)
                next_agent_state = ResourceAllocationState(next_state.server_tasks[server], server, next_state.time_step)

                server_weighting_agents[server].resource_allocation_obs(agent_state, weighting_actions[server],
                                                                        next_agent_state, finished_server_tasks[server])
        assert all(task.auction_time <= next_state.time_step <= task.deadline
                   for _, tasks in next_state.server_tasks.items() for task in tasks)
        # Update the state with the next state
        state = next_state


def set_policy(task_pricing_agents: List[TaskPricingRLAgent],
               resource_weighting_agents: List[ResourceWeightingRLAgent], policy: bool):
    """
    Sets the action selection policy either epsilon greedy or argmax

    Args:
        task_pricing_agents: List of task pricing agents
        resource_weighting_agents: List of resource weighting agents
        policy: Action selection policy
    """
    for task_pricing_agent in task_pricing_agents:
        task_pricing_agent.eval_policy = policy
    for resource_weighting_agent in resource_weighting_agents:
        resource_weighting_agent.eval_policy = policy


def run_training(training_env: OnlineFlexibleResourceAllocationEnv, eval_envs: List[str],
                 total_episodes: int, task_pricing_agents: List[TaskPricingRLAgent],
                 resource_weighting_agents: List[ResourceWeightingRLAgent], eval_frequency: int):
    """
    Runs the training of the agents for a fixed number of episodes

    Args:
        training_env: The training environments
        eval_envs: The evaluation environment filenames
        total_episodes: The total number of episodes
        task_pricing_agents: The task pricing agents
        resource_weighting_agents: The resource weighting agents
        eval_frequency: The evaluation frequency
    """
    # Loop over the episodes
    for episode in range(total_episodes):
        print(f'Episode: {episode} at {dt.datetime.now().strftime("%H:%M:%S")}')
        set_policy(task_pricing_agents, resource_weighting_agents, False)
        train_agent(training_env, task_pricing_agents, resource_weighting_agents)

        # Every eval_frequency episodes, the agents are evaluated
        if episode % eval_frequency == 0:
            set_policy(task_pricing_agents, resource_weighting_agents, True)
            eval_agent(eval_envs, episode, task_pricing_agents, resource_weighting_agents)

            print('\tTP Total Obs: {' + ', '.join(f'{agent.name}: {agent.total_obs}' for agent in task_pricing_agents) + '}')
            print('\tRW Total Obs: {' + ', '.join(f'{agent.name}: {agent.total_obs}' for agent in resource_weighting_agents) + '}')
            print()


def generate_eval_envs(eval_env: OnlineFlexibleResourceAllocationEnv, num_evals: int, folder: str,
                       overwrite: bool = False) -> List[str]:
    """
    Generates and saves the evaluation environment used for evaluating training of the agents

    Args:
        eval_env: The evaluation environment used to generate the files
        num_evals: The number of environments generated
        folder: The folder where the environments are generated
        overwrite: If to overwrite previous environments saved

    Returns: A list of environment file paths
    """
    if not os.path.exists(folder):
        os.makedirs(folder)

    eval_files = []
    for eval_num in range(num_evals):
        eval_file = f'{folder}/eval_{eval_num}.json'
        eval_files.append(eval_file)
        if overwrite or not os.path.exists(eval_file):
            eval_env.reset()
            eval_env.save_env(eval_file)

    return eval_files


def setup_tensorboard(folder: str) -> ResourceSummaryWriter:
    """
    Setups the tensorboard for the training and evaluation results

    Args:
        folder: The folder for the tensorboard
    """
    return tf.summary.create_file_writer(f'train_agents/results/logs/{folder}_{dt.datetime.now().strftime("%m-%d_%H-%M-%S")}')