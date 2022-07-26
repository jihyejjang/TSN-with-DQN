import numpy as np
import random
from random import randrange
from collections import deque
from ddqn import DoubleDeepQNetwork
import warnings
from utils import *
warnings.filterwarnings('ignore')


class Agent:  
    def __init__(self,args):
        self.max_episode = args.totalepisode
        self.model = DoubleDeepQNetwork(args)
        self.epsilon = EPSILON_MAX
        self.memory = deque(maxlen=999999999999999)

    def reset(self):
        self._epsilon_decay_()
        return self.epsilon

    def choose_action(self, state):
        if np.random.random() < self.epsilon:
            id = randrange(ACTION_SIZE)
            action = id
            return action
        else:
            n = self.model.predict_one(state)
            id = np.argmax(n)
            action = id
            return action

    def _epsilon_decay_(self):
        if self.epsilon > EPSILON_MIN:
            self.epsilon -= EPSILON_MAX/self.max_episode
        else:
            self.epsilon = EPSILON_MIN

    def sample(self):  
        sample_batch = random.sample(self.memory, BATCH)
        return sample_batch

    def observation(self, state, action_id, reward, next_state, done):  
        sample = [state, action_id, reward, next_state, done]
        self.memory.append(sample)

    def state_target(self, batch):  # data split

        states = np.array([o[0] for o in batch])
        states_ = np.array([o[3] for o in batch])  # next state

        p = self.model.predict(states)  # model predict with state
        p_ = self.model.predict(states_)
        pTarget_ = self.model.predict(states_, target=True)  # target_model predict with next state

        x = np.zeros((BATCH, INPUT_SIZE))
        y = np.zeros((BATCH, ACTION_SIZE))
        # errors = np.zeros(batch_len)

        for i in range(BATCH):
            o = batch[i]  # batch=[state, action, reward, next_state, done]
            s = o[0]
            a = o[1]
            # a = action_to_number(o[1])
            r = o[2]
            # ns = o[3]
            done = o[4]

            t = p[i]
            # old_value = t[a]
            if done:
                t[a] = r
            else:
                t[a] = r + DISCOUNT_FACTOR * pTarget_[i][np.argmax(p_[i])] # ddqn differs with dqn at this point

            x[i] = s
            y[i] = t

        return [x, y]

    # build the replay buffer 
    def replay(self):

        if len(self.memory) < BATCH:
            return 99999

        batch = self.sample()
        x, y = self.state_target(batch)
        min_loss = self.model.train(x, y)

        return min_loss

    def update_target_model(self):
        self.model.update_target_model()
