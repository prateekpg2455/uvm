from flask import Response, Flask, request, jsonify, render_template, make_response, url_for,redirect, send_from_directory
import json
# from flask.ext.socketio import SocketIO, emit
from collections import defaultdict
from flask_sockets import Sockets

class setup(object):
    def __init__(self):
        self.vars = {}

    def save(self):
        tmp = open('./static/parameters.json', 'w')
        json.dump(self.vars, tmp)
        tmp.close()

class learnedObjectsVars(object):
    def __init__(self):
        self.vars = {}
        self.vars['OPTIMAL_Q'] = {}
        self.vars['OPTIMAL_V'] = {}
        self.observation = {}

    def save(self):
        json.dump(self.vars,open('./static/learnedObjects.json', 'w'))

    def updateQ(self, prev_state, next_state, action, reaction):
        # update equation
        Q = self.vars['Q'] # it makes a copy
        Q[prev_state][action] = Q[prev_state][action] + \
                    setupVars.vars['ALPHA'] *( setupVars.vars['REACTION_REWARD'][action][reaction] + setupVars.vars['GAMMA']* max(Q[next_state].itervalues()) - Q[prev_state][action] )

    def recordPolicy(self, prev_state, action):
        self.vars['EXECUTED_POLICY'][prev_state][action]+=1

    def updateVandPolicy(self):
        self.vars['OPTIMAL_POLICY'], self.vars['V'] = optimizePolicy(self.vars['Q'])

    def recordPageValue(self, url, prev_state, next_state, action):
        if url not in self.vars['pages']:
            self.vars['pages'][url] = {a: {'sum':0, 'obs':0} for a in setupVars.vars['ACTIONS']}

        self.vars['pages'][url][action]['sum'] +=  self.vars['V'][prev_state] + self.vars['V'][next_state]
        self.vars['pages'][url][action]['obs'] += 1

    def recordTransitionProbs(self, prev_state, action, reaction):
        self.observation[prev_state] = True
        # print self.observation.keys()
        self.vars['transitionProbs'][prev_state][action]['obs']+=1
        self.vars['transitionProbs'][prev_state][action][reaction] +=1


    def getSARSAOptimizedPolicy(self, epsilon, iterations):
        current_policy = self.vars['OPTIMAL_POLICY'].copy()
        Q = self.vars['Q'].copy()
        P = self.vars['transitionProbs']

        #simulation of several episodes
        print "Optimizing using SARSA"
        for i in range(iterations):
            print i
            #episode
            s0 = 1
            action0 = decideAction(current_policy[s0], setupVars.vars['ACTIONS'], epsilon)
            while s0 != 1000:
                reaction = weighted_choice([(r,v)  for r,v in P[s0][action0].iteritems() if r!='obs'])
                reward = setupVars.vars['REACTION_REWARD'][action0][reaction]
                s1 = getNewCell(s0, reaction)
                if s1 ==s0:
                    continue
                action1 = decideAction(current_policy[s1], setupVars.vars['ACTIONS'], epsilon)

                Q[s0][action0] = Q[s0][action0] + setupVars.vars['ALPHA'] * (reward + setupVars.vars['GAMMA']* Q[s1][action1] - Q[s0][action0])
                print s0, '-->', s1
                s0 = s1
                action0 = action1
            print '------------------'

        current_policy, V  = optimizePolicy(Q)
        self.vars['OPTMAL_Q'] = Q
        self.vars['OPTIMAL_V'] = V

    def readyForSARSA(self):
        # print set(self.vars['Q'].keys()) - set([1000]) - set(self.observation.keys())
        return len(set(self.vars['Q'].keys()) - set([1000]) - set(self.observation.keys()) ) == 0

def decideAction(action,actions, epsilon):
    # epsilon / len(actions) to all and 1-epsilon to action additional
    weights = [(a, [epsilon/len(actions), 1- epsilon + epsilon/len(actions) ][a==action]) for a in actions]
    return weighted_choice(weights)

def weighted_choice(choices):
   total = sum(w for c, w in choices)
   r = random.uniform(0, total)
   upto = 0
   for c, w in choices:
      if upto + w >= r:
          return c
      upto += w
   assert False, "Shouldn't get here"

def optimizePolicy(Q):
    policy = {}
    V = {}
    for cell in Q:
        _max =  max(Q[cell].iteritems(), key= lambda x:x[1])
        V[cell] = _max[1]
        policy[cell] = _max[0]
    return policy, V


def getNewCell(s,reaction):
    if reaction == 'dead':
        return 1000

    if s % setupVars.vars['MAX_ATSOP_ROWS'] == 0 :
        if reaction == 'down':
            return s
    if 1 + s/setupVars.vars['MAX_ATSOP_ROWS'] >= setupVars.vars['MAX_SD_COLS']:
        if reaction == 'right':
            return s

    if reaction == 'right':
        return s + setupVars.vars['MAX_ATSOP_ROWS']

    if reaction == 'down':
        return s + 1


setupVars = setup()
learnedObjects = learnedObjectsVars()

import random
app = Flask(__name__)
sockets = Sockets(app)

@app.route('/', methods=['GET', 'POST'])
def welcome():
    return render_template('landingPage.html')

@app.route('/mdp_setup', methods=['GET', 'POST'])
def mdp_setup():
    return render_template('mdp_index.html')

@app.route('/getNews', methods=['GET', 'POST'])
def getNews():
    return jsonify(news['news'])

@app.route('/loadSetup', methods=['POST'])
def loadSetup():
    json.dump( {},open('userData.json','w'))

    data = request.json

    ACTIONS = data['action'].keys()
    REACTION_REWARD = {x:{y:float(v) for y,v in data['action'][x].iteritems() if y!= 'use_rate' } for x in data['action']}
    USED_POLICY = {x:[float(v) for y,v in data['action'][x].iteritems() if y== 'use_rate'][0]  for x in data['action'] }

    # normalize policy
    total = sum(USED_POLICY.values())
    USED_POLICY = {x:v/total for x,v in USED_POLICY.iteritems()}

    setupVars.vars['ACTIONS']  = ACTIONS
    setupVars.vars['REACTION_REWARD'] = REACTION_REWARD
    setupVars.vars['USED_POLICY'] = USED_POLICY
    setupVars.vars['MAX_ATSOP_ROWS'] = int(data['params']['MAX_ATSOP_ROWS'])
    setupVars.vars['MAX_SD_COLS'] = int(data['params']['MAX_SD_COLS'])
    setupVars.vars['ATSOP_GAP'] = int(data['params']['ATSOP_GAP'])
    setupVars.vars['GAMMA'] =float(data['params']['GAMMA'])
    setupVars.vars['ALPHA'] =float(data['params']['ALPHA'])

    setupVars.save()

    ncells = setupVars.vars['MAX_ATSOP_ROWS'] * setupVars.vars['MAX_SD_COLS']

    ncells = [x for x in range(ncells)] + [999]
    Q = {x+1:{x:0.0 for x in ACTIONS} for x in ncells}
    EXECUTED_POLICY = {x+1:{x:0.0 for x in ACTIONS} for x in ncells}

    learnedObjects.vars['Q'] = Q
    learnedObjects.vars['OPTIMAL_POLICY'] = {x+1:'n' for x in ncells}
    learnedObjects.vars['V'] = {x+1: 0 for x in ncells}
    learnedObjects.vars['EXECUTED_POLICY'] = EXECUTED_POLICY
    learnedObjects.vars['pages'] =defaultdict(dict)
    learnedObjects.vars['transitionProbs'] = {x+1:{action:{'obs':3,'down':1,'right':1,'dead':1 } for action in setupVars.vars['ACTIONS']} for x in ncells }

    learnedObjects.save()

    return str(url_for('welcome'))

@app.route('/loadHome', methods=['GET'])
def home():
    cookie = request.headers['Cookie']
    if cookie not in user_data:
        user_data[cookie] = {'atsop_mean': 150000, 'sd_mean':5, 'catsop':150000, 'visits':1}

    json.dump( user_data,open('userData.json','w'))

    data = user_data[cookie]
    categories = news['news'].keys()
    # parameters = json.loads(open('./static/parameters.json').read())
    return render_template('index.html', news=news['news'], categories = categories)

@app.route('/feedback', methods=['POST'])
def updates():
    data = request.json # it has prev_state,next_state, action, reaction

    # update Q
    for i in data['feedback1']:
        learnedObjects.updateQ(i['prev_state'], i['next_state'], i['action'],i['reaction'])
        learnedObjects.recordPolicy(i['prev_state'], i['action'])
        learnedObjects.recordPageValue(i['url'], i['prev_state'], i['next_state'], i['action'])
        learnedObjects.recordTransitionProbs(i['prev_state'], i['action'], i['reaction'])

    # find out optimal policy & find out V
    learnedObjects.updateVandPolicy()


    if learnedObjects.readyForSARSA():
        print "SARSA"
        learnedObjects.getSARSAOptimizedPolicy(0.3,1000)

    setupVars.save()
    learnedObjects.save()

    return "sdf"

@app.route('/getQ')
def getQ():
    out = defaultdict(list)

    # convert the Q dictionary in the format of heatmap
    for a in setupVars.vars['ACTIONS']:
        for i in learnedObjects.vars['Q']:
            if i <= setupVars.vars['MAX_ATSOP_ROWS']:
                row = [ learnedObjects.vars['Q'][i+x*setupVars.vars['MAX_ATSOP_ROWS']][a]  for x in range(setupVars.vars['MAX_SD_COLS'])]
                out[a].append(row)
            else:
                break
        out[a] = out[a][::-1] # so that heatpmap is displayed top(0s) to bottom(max number fof seconds)
    return jsonify(out)

@app.route('/getV')
def getV():
    out = []
    for i in learnedObjects.vars['V']:
        if i <= setupVars.vars['MAX_ATSOP_ROWS']:
            row = [ learnedObjects.vars['V'][i+x*setupVars.vars['MAX_ATSOP_ROWS']] for x in range(setupVars.vars['MAX_SD_COLS'])]
            out.append(row)
        else:
            break
    value = out[0][0]
    out = out[::-1] # so that heatpmap is displayed top(0s) to bottom(max number fof seconds)
    return jsonify({'V' :out, 'value':value})

@app.route('/getPolicy')
def getPolicy():
    SARSA = learnedObjects.readyForSARSA()

    out1,out2 = [],[]
    actions = {x[0]:e for e,x in enumerate(setupVars.vars['ACTIONS'])}

    for i in learnedObjects.vars['V']:
        if i <= setupVars.vars['MAX_ATSOP_ROWS']:
            tmp1,tmp2 = [],[]
            for x in range(setupVars.vars['MAX_SD_COLS']):
                a  = learnedObjects.vars['OPTIMAL_POLICY'][i+x*setupVars.vars['MAX_ATSOP_ROWS']]

                tmp1.append(actions[a[0]])
                tmp2.append(a[0])

            out1.append(tmp1)
            out2.append(tmp2)
        else:
            break
    out1,out2 = out1[::-1], out2[::-1]
    # so that heatpmap is displayed top(0s) to bottom(max number fof seconds)
    return jsonify({'policy' :out2, 'number':out1, 'SARSA':SARSA})

@app.route('/getUsedPolicy')
def getUsedPolicy():
    p = learnedObjects.vars['EXECUTED_POLICY'].copy()
    #normalize
    for i in p:
        total = sum(p[i].values())
        _max= max(p[i].iteritems(), key=lambda x:x[1])
        p[i] = (_max[0], round(1.0*_max[1]/(1+total),1))

    out1,out2 = [],[]
    actions = {x[0]:e for e,x in enumerate(setupVars.vars['ACTIONS'])}
    for i in learnedObjects.vars['V']:
        if i <= setupVars.vars['MAX_ATSOP_ROWS']:
            tmp1,tmp2 = [],[]
            for x in range(setupVars.vars['MAX_SD_COLS']):
                a  = p[i+x*setupVars.vars['MAX_ATSOP_ROWS']]
                tmp1.append(actions[a[0][0]])
                tmp2.append(str(a[0][0])+" "+ str(a[1]))

            out1.append(tmp1)
            out2.append(tmp2)
        else:
            break
    out1,out2 = out1[::-1], out2[::-1]
    # so that heatpmap is displayed top(0s) to bottom(max number fof seconds)
    return jsonify({'policy' :out2, 'number':out1})

@app.route('/getPages')
def getPages():
    out = {}
    pages = learnedObjects.vars['pages']
    actions = setupVars.vars['ACTIONS']
    for i in pages:
        out[i]  = {action: round(1.0*pages[i][action]['sum']/ (1+pages[i][action]['obs']),2) for action in actions}
    return jsonify({'pages': out })

@app.route('/getOptV')
def getOptV():
    out = []
    if learnedObjects.readyForSARSA():

        for i in learnedObjects.vars['OPTIMAL_V']:
            if i <= setupVars.vars['MAX_ATSOP_ROWS']:
                row = [ learnedObjects.vars['OPTIMAL_V'][i+x*setupVars.vars['MAX_ATSOP_ROWS']] for x in range(setupVars.vars['MAX_SD_COLS'])]
                out.append(row)
            else:
                break
        out =  out[::-1] # so that heatpmap is displayed top(0s) to bottom(max number fof seconds)
    print out
    return jsonify({'OptV' :out})

if __name__ == "__main__":
    news = {'news': json.load(open('./static/news.json'))}
    user_data = json.load(open('userData.json'))

    app.run('0.0.0.0', 9090, debug=True)
