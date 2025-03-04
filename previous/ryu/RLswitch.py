
import time
import pandas as pd
from ryu.lib import hub
from ryu import utils
from multiprocessing import Process

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, HANDSHAKE_DISPATCHER
from ryu.controller.handler import set_ev_cls

from ryu.ofproto import ofproto_v1_3

from ryu.lib.packet import packet, ether_types, in_proto
from ryu.lib.packet import ethernet, icmp, ipv4, ipv6
import numpy as np

#from tensorflow import keras

def addr_table():  # address table dictionary is created manually
    H = ['00:00:00:00:00:0' + str(h) for h in range(1, 9)]  # hosts
    mac_to_port = {}  # switch는 6개, src는 8개가 존재
    port = [[1, 2, 3, 3, 3, 3, 3, 3],
            [3, 3, 1, 2, 3, 3, 3, 3],
            [1, 1, 2, 2, 3, 3, 3, 3],
            [1, 1, 1, 1, 2, 2, 3, 3],
            [1, 1, 1, 1, 2, 3, 1, 1],
            [1, 1, 1, 1, 1, 1, 2, 3]]  # custom topology에 해당하는 swith,port mapping 정보

    for s in range(1, 7):  # 6 switches
        mac_to_port.setdefault(s, {})
        for h in range(len(H)): #0~7
            mac_to_port[s][H[h]] = port[s - 1][h]
    return mac_to_port

class rl_switch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(rl_switch, self).__init__(*args, **kwargs)

        #self.model1 = keras.models.load_model("agent17.900466698629316e-07.h5")
        #self.model2 = keras.models.load_model("agent27.900466698629316e-07.h5")
        #self.model3 = keras.models.load_model("agent37.900466698629316e-07.h5")
        #self.model4 = keras.models.load_model("agent47.900466698629316e-07.h5")

        self.generated_log = pd.DataFrame(columns=['switch','class','number','time','queue'])#{'switch','class','arrival time','queue'}
        # self.received_log = pd.DataFrame(columns=['arrival time','switch','class','number','delay','queue'])
        self.terminal = False
        #self.start_time=datetime.now()
        self.first = True
        self.state=np.zeros((6,4))
        self.mac_to_port = addr_table()
        self.H = ['00:00:00:00:00:0' + str(h) for h in range(1, 9)]  # hosts
        self.dp={}
        self.queue = np.zeros((6,3,4)) #switch, (output)port, priority queue
        self.timeslot_size = 0.5 #ms
        self.cycle = 10
        self.ts_cnt=0
        # self.gcl = {1: ['0000000000', '0000000000', '0000000000', '1000000000'],
        #             2: ['0000000000', '0000000000', '0000000000', '1111111111'],
        #             3: ['0000000000', '0000000000', '0000000000', '1111111111'],
        #             4: ['0000000000', '0000000000', '0000000000', '1111111111'],
        #             5: ['0000000000', '0000000000', '0000000000', '1111111111'],
        #             6: ['0000000000', '0000000000', '0000000000', '1111111111']} #최초 action
        self.gcl = {1: ['1111111111', '1111111111', '1111111111', '1111111111'],
                    2: ['1111111111', '1111111111', '1111111111', '1111111111'],
                    3: ['1111111111', '1111111111', '1111111111', '1111111111'],
                    4: ['1111111111', '1111111111', '1111111111', '1111111111'],
                    5: ['1111111111', '1111111111', '1111111111', '1111111111'],
                    6: ['1111111111', '1111111111', '1111111111', '1111111111']
                    } #최초 action

        self.gcl_={1: np.array([list(l) for l in self.gcl[1]]),
                   2: np.array([list(l) for l in self.gcl[2]]),
                   3: np.array([list(l) for l in self.gcl[3]]),
                   4: np.array([list(l) for l in self.gcl[4]]),
                   5: np.array([list(l) for l in self.gcl[5]]),
                   6: np.array([list(l) for l in self.gcl[6]])
                   }

        # flow attribute
        #self.best_effort = 30  # best effort traffic (Even)
        #self.cnt1 = 0  # 전송된 flow 개수 카운트
        self.command_control = 20  # c&c flow number (Even)
        self.cc_cnt = 0
        self.cc_cnt2 = 0
        self.video = 2  # video flow number (Even)
        self.vd_cnt = 0
        self.vd_cnt2 = 0
        self.audio = 8  # audio flow number (Even)
        self.ad_cnt = 0
        self.ad_cnt2 = 0
        self.cc_period = 5  # to 80
        self.vd_period = 33
        self.ad_period = 1  # milliseconds

        self.timeslot_start = 0

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        self.dp[datapath.id]=datapath
        self.logger.info("스위치 %s 연결" %  datapath.id)

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(port=ofproto.OFPP_CONTROLLER,
                                          max_len=ofproto.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        self.add_flow(datapath,0,match,0,inst)

        if len(self.dp)==6:
            hub.sleep(3)
            self.timeslot_start = time.time()
            #self.action_thread = hub.spawn(self.gcl_cycle)
            self.action_1 = hub.spawn(self.gcl_3)
            self.action_2 = hub.spawn(self.gcl_4)
            self.action_3 = hub.spawn(self.gcl_5)
            # self.action_4 = hub.spawn(self.gcl_6)
            self.cc_thread = hub.spawn(self._cc_gen1)
            # self.cc_thread2 = hub.spawn(self._cc_gen2)
            self.ad_thread = hub.spawn(self._ad_gen1)
            # self.ad_thread2 = hub.spawn(self._ad_gen2)
            # self.vd_thread =  hub.spawn(self._vd_gen1)
            # self.vd_thread2 = hub.spawn(self._vd_gen2)


    #TODO: GCL 적용하기

    # def gcl_update(self):
    #
    # def _request_stats(self, datapath):
    #     self.logger.debug('send stats request: %016x', datapath.id)
    #     ofproto = datapath.ofproto
    #     parser = datapath.ofproto_parser
    #
    #     req = parser.OFPFlowStatsRequest(datapath)
    #     datapath.send_msg(req)
    #
    #     req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
    #     datapath.send_msg(req)
    #
    # @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    # def _flow_stats_reply_handler(self, ev):
    #     body = ev.msg.body
    #
    #     self.logger.info('datapath         '
    #                      'in-port  eth-dst           '
    #                      'out-port packets  bytes')
    #     self.logger.info('---------------- '
    #                      '-------- ----------------- '
    #                      '-------- -------- --------')
    #     for stat in sorted([flow for flow in body if flow.priority == 1],
    #                        key=lambda flow: (flow.match['in_port'],
    #                                          flow.match['eth_dst'])):
    #         self.logger.info('%016x %8x %17s %8x %8d %8d',
    #                          ev.msg.datapath.id,
    #                          stat.match['in_port'], stat.match['eth_dst'],
    #                          stat.instructions[0].actions[0].port,
    #                          stat.packet_count, stat.byte_count)

    def timeslot(self, time):  # timeslot 진행 횟수를 알려주는 함수
        msec = round((time - self.timeslot_start)*1000,1)
        slots = int(msec / self.timeslot_size)
        cyc = int(slots / self.cycle)
        clk = cyc % self.cycle
        return cyc, clk

    def gcl_3(self):
        hub.sleep(3.05)
        datapath = self.dp[3]
        #ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        while True:
            goto = parser.OFPInstructionGotoTable(1)
            _,clk = self.timeslot(time.time())
            gate=self.gcl_[datapath.id][:,clk]
            # print("gate:",gate)

            #class 1
            #match1 = parser.OFPMatch(eth_type=0x05dc)
            match1 = parser.OFPMatch(in_port = 1, eth_dst = self.H[4])
            if gate[0] == '0' :
                action1 = parser.OFPInstructionGotoTable(2)
            else :
                action1 = goto
            #print(action1)
            self.add_flow_(datapath, 1000, match1, 0, [action1])

            # class 2
            match2 = parser.OFPMatch(in_port = 1, eth_dst = self.H[5])
            if gate[1] == '0':
                action2 = parser.OFPInstructionGotoTable(2)
            else :
                action2 = goto
            #print(action2)
            self.add_flow_(datapath, 1000, match2, 0, [action2])

            # class 3
            # match3 = parser.OFPMatch()
            # if gate[2] == '0':
            #     action3 = parser.OFPInstructionGotoTable(2)
            # else :
            #     action3 = goto
            # #print(action3)
            # self.add_flow(datapath, 1000, match3, 0, [action3])

            #TODO : class 4

            hub.sleep(0.0004)

            if self.terminal == 6:
                self.generated_log.to_csv('switchlog0818_generated.csv')

    def gcl_4(self):
        hub.sleep(3.05)
        datapath = self.dp[4]
        #ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        while True:
            goto = parser.OFPInstructionGotoTable(1)
            _,clk = self.timeslot(time.time())
            gate=self.gcl_[datapath.id][:,clk]
            # print("gate:",gate)

            #class 1
            match1 = parser.OFPMatch(in_port=1, eth_dst=self.H[4])
            if gate[0] == '0':
                action1 = parser.OFPInstructionGotoTable(2)
            else:
                action1 = goto
            # print(action1)
            self.add_flow_(datapath, 1000, match1, 0, [action1])

            # class 2
            match2 = parser.OFPMatch(in_port=1, eth_dst=self.H[5])
            if gate[1] == '0':
                action2 = parser.OFPInstructionGotoTable(2)
            else:
                action2 = goto
            # print(action2)
            self.add_flow_(datapath, 1000, match2, 0, [action2])

            # # class 3
            # match3 = parser.OFPMatch(eth_type=0x88e7)
            # if gate[2] == '0':
            #     action3 = parser.OFPInstructionGotoTable(2)
            # else :
            #     action3 = goto
            # #print(action3)
            # self.add_flow_(datapath, 1000, match3, 0, [action3])

            #TODO : class 4

            hub.sleep(0.0004)

    def gcl_5(self):
        hub.sleep(3.05)
        datapath = self.dp[5]
        #ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        while True:
            goto = parser.OFPInstructionGotoTable(1)
            _,clk = self.timeslot(time.time())
            gate=self.gcl_[datapath.id][:,clk]
            # print("gate:",gate)

            #class 1
            match1 = parser.OFPMatch(in_port=1, eth_dst=self.H[4])
            if gate[0] == '0':
                action1 = parser.OFPInstructionGotoTable(2)
            else:
                action1 = goto
            # print(action1)
            self.add_flow_(datapath, 1000, match1, 0, [action1])

            # class 2
            match2 = parser.OFPMatch(in_port=1, eth_dst=self.H[5])
            if gate[1] == '0':
                action2 = parser.OFPInstructionGotoTable(2)
            else:
                action2 = goto
            # print(action2)
            self.add_flow_(datapath, 1000, match2, 0, [action2])

            # class 3
            # match3 = parser.OFPMatch(eth_type=0x88e7)
            # if gate[2] == '0':
            #     action3 = parser.OFPInstructionGotoTable(2)
            # else :
            #     action3 = goto
            # #print(action3)
            # self.add_flow_(datapath, 1000, match3, 0, [action3])

            #TODO : class 4

            hub.sleep(0.0004)

    def gcl_6(self):
        hub.sleep(3.05)
        datapath = self.dp[6]
        #ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        while True:
            goto = parser.OFPInstructionGotoTable(1)
            _,clk = self.timeslot(time.time())
            gate=self.gcl_[datapath.id][:,clk]
            # print("gate:",gate)

            #class 1
            match1 = parser.OFPMatch(eth_type=0x05dc)
            if gate[0] == '0' :
                action1 = parser.OFPInstructionGotoTable(2)
            else :
                action1 = goto
            #print(action1)
            self.add_flow_(datapath, 1000, match1, 0, [action1])

            # class 2
            match2 = parser.OFPMatch(eth_type=0x88a8)
            if gate[1] == '0':
                action2 = parser.OFPInstructionGotoTable(2)
            else :
                action2 = goto
            #print(action2)
            self.add_flow_(datapath, 1000, match2, 0, [action2])

            # class 3
            match3 = parser.OFPMatch(eth_type=0x88e7)
            if gate[2] == '0':
                action3 = parser.OFPInstructionGotoTable(2)
            else :
                action3 = goto
            #print(action3)
            self.add_flow_(datapath, 1000, match3, 0, [action3])

            #TODO : class 4

            hub.sleep(0.0004)


    # def gcl_cycle(self):
    #     time.sleep(0.005)
    #
    #     while True:
    #         time.sleep(0.001 * self.timeslot_size * 9)
    #         #state 관측
    #         #TODO: state 수정
    #         for switch in range(len(self.state)):
    #             for queue in range(len(self.state[0])): #switch 별 state : len(state[0]) = 4
    #                 self.state[switch][queue] = sum(self.queue[switch, :, queue])
    #
    #         for s in range(len(self.dp)):
    #             self.gcl[s] = [format(np.argmax(self.model1.predict(self.state[s].reshape(-1,4))), '010b'),
    #                    format(np.argmax(self.model2.predict(self.state[s].reshape(-1,4))), '010b'),
    #                    format(np.argmax(self.model3.predict(self.state[s].reshape(-1,4))), '010b'),
    #                    format(np.argmax(self.model4.predict(self.state[s].reshape(-1,4))), '010b')]
    #             print(self.gcl[s])
    #
    @set_ev_cls(ofp_event.EventOFPErrorMsg,
                [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def error_msg_handler(self, ev):
        msg = ev.msg

        self.logger.debug('OFPErrorMsg received: type=0x%02x code=0x%02x ',
                          msg.type, msg.code)

    def add_flow_(self, datapath, priority, match, tableid, inst):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        mod = parser.OFPFlowMod(datapath=datapath, table_id = tableid, priority=priority, command = ofproto.OFPFC_MODIFY,
                                    match=match, instructions = inst)
        datapath.send_msg(mod)

    def add_flow(self, datapath, priority, match, tableid, inst):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        mod = parser.OFPFlowMod(datapath=datapath, table_id = tableid, priority=priority, command = ofproto.OFPFC_ADD,
                                    match=match, instructions = inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        #fields = msg.match.fields
        #print(fields)
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        # for f in fields:
        #     if f.header == ofproto.OXM_OF_IN_PORT:
        #         in_port = f.value
        #         print ("in_port",in_port)
        #     elif f.header == ofproto.OXM_OF_ETH_SRC:
        #         eth_src = f.value
        #         print("eth_src",eth_src)
        #     elif f.header == ofproto.OXM_OF_ETH_DST:
        #         eth_dst = f.value
        #         print("eth_dst", eth_dst)
        #     elif f.header == ofproto.OXM_OF_ETH_TYPE:
        #         et_ty = f.value
        #         print("eth_type", et_ty)

        #table_id = msg.table_id
        #fields = msg.match.fields
        switchid = datapath.id
        #bufferid = msg.buffer_id

        #print ("table_id", table_id)
        #print ("fields", fields)

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        eth_type_ = eth.ethertype
        #print("packet in", eth.ethertype)
        dst = eth.dst
        #print("eth.dst",dst)
        src = eth.src
        #print("eth.src",src)
        #print("ofproto.OXM_OF_IN_PORT",ofproto.OXM_OF_IN_PORT)
        #print("ofproto.OXM_OF_ETH_SRC",ofproto.OXM_OF_ETH_SRC)

        class_ = 4 #best effort
        #print("dst",dst)
        match = parser.OFPMatch(in_port = in_port, eth_dst=dst)
        if (dst in self.H) and (src in self.H):
            #print("dd")
            if eth_type_ == ether_types.ETH_TYPE_IEEE802_3:
                match1 = parser.OFPMatch(eth_type=0x05dc)
                #match = parser.OFPMatch(in_port=in_port)
                class_ = 1
                #print("class_1, inport",in_port)
                # type_ = 0x05dc
                #self.logger.info("class %s packet" % (class_))
            elif eth_type_ == ether_types.ETH_TYPE_8021AD:
                match1 = parser.OFPMatch(eth_type=0x88a8)
                #match = parser.OFPMatch(in_port=in_port)
                class_ = 2
                #print("class_2,inport",in_port)
                # type_ = 0x88a8
                #self.logger.info("class %s packet" % (class_))
            elif eth_type_ == ether_types.ETH_TYPE_8021AH:
                match1 = parser.OFPMatch(eth_type=0x88e7)
                #match = parser.OFPMatch(in_port=in_port)
                class_ = 3
                #print("class_3,inport",in_port)
                # type_ = 0x88e7
                #self.logger.info("class %s packet" % (class_))

        else :
            self.add_flow(datapath, 1, match, 0, [])
            return

        if dst in self.mac_to_port[switchid]:
            out_port = self.mac_to_port[switchid][dst]
            #print("inport %s,out_port %s" % (in_port, out_port))
            # self.queue[switchid - 1][out_port - 1][class_ - 1] += 1
        else:
            out_port = ofproto.OFPP_FLOOD

        actions1 = parser.OFPActionOutput(out_port)
        goto = parser.OFPInstructionGotoTable(1) # 1: sending packet to port, 2: queueing packet
        actions2 = parser.OFPActionSetQueue(out_port)
        #actions2 = parser.OFPActionOutput(out_port)
        inst1 = parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, [actions1])
        inst2 = parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, [actions2])

        self.add_flow(datapath, 100, match, 1, [inst1])
        self.add_flow(datapath, 100, match, 2, [inst2])
        self.add_flow(datapath, 100, match, 0, [goto])

        #self.thread.append(hub.spawn(self._gcl_, datapath, match))

        #print("add_flow")

        # if out_port != ofproto.OFPP_FLOOD:
        #     match = parser.OFPMatch(in_port=in_port, eth_type=type_)
        #     if class_ != 4 :
        #         self.add_flow(datapath, 1000, match, actions)
        #         print("add flow entry")
        # if msg.buffer_id != ofproto.OFP_NO_BUFFER:
        #     # self.add_flow(datapath, 1000, match, actions)
        #     return

        # while True:
        #     try:
        # delay = (self.gcl[switchid][class_-1][clk - 1:].index('1')) * self.timeslot_size  # gate가 open되기까지의 시간을 계산 (만약 열려있으면 바로 전송)
                # break
            # except:
            #     print("다음 cycle까지 기다리기 : 현재 사이클에 OPEN예정이 없음")
            #     time.sleep(self.timeslot_size/1000)

        #print("delay", delay/1000)

        # hub.sleep(delay/1000) #delay

        # match = parser.OFPMatch(in_port = in_port)
        #flow가 match와 일치하면 match생성시에 지정해준 action으로 packet out한다.
        # delay_end_time = 0
        # if msg.buffer_id == ofproto.OFP_NO_BUFFER:
        #     delay_end_time = time.time()
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=[actions1], data=pkt.data)

        datapath.send_msg(out)


        # if (1 <= out_port <= 3):
        #     self.queue[switchid-1][out_port-1][class_-1] -= 1
        #     df = pd.DataFrame([(delay_end_time, switchid, class_, '-', delay_end_time - delay_start_time,
        #                         self.queue[switchid - 1][out_port - 1][class_ - 1])],
        #                       columns=['arrival time', 'switch', 'class', 'number', 'delay', 'queue'])
        #     self.received_log = self.received_log.append(df)

        if class_ != 4:
            self.logger.info("[in] %f : 스위치 %s, class %s 패킷" % \
                                 (time.time(), switchid, class_))

    #flow generating thread
    def _cc_gen1(self):
        hub.sleep(3)
        datapath = self.dp[1]
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_IEEE802_3,
                                           dst=self.H[5],
                                           src=self.H[1]))

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        while True:
            self.cc_cnt += 1
            #match = parser.OFPMatch(in_port=2, eth_type=0x05dc, eth_dst=self.H[5])
            actions = [parser.OFPActionOutput(3)]
            #inst = parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
            #self.add_flow(datapath, 1000, match, 0, [inst])
            pkt.serialize()
            out = parser.OFPPacketOut(datapath=datapath,
                                      buffer_id=ofproto.OFP_NO_BUFFER,
                                      in_port = 2,
                                      actions=actions, data=pkt.data)
            datapath.send_msg(out)
            self.logger.info("%f : %s번 째 C&C1 generated in switch%s " % (time.time(), self.cc_cnt, datapath.id))
            df = pd.DataFrame([(datapath.id, 1, self.cc_cnt, time.time(), 'x')],
                              columns=['switch', 'class', 'number', 'time', 'queue'])
            self.generated_log = self.generated_log.append(df)
            hub.sleep(self.cc_period / 1000)

            if (self.cc_cnt >= self.command_control):
                self.terminal += 1
                if self.terminal == 6:
                    self.generated_log.to_csv('switchlog0818_generated.csv')
                break

    def _cc_gen2(self):
        hub.sleep(3)
        datapath = self.dp[2]
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_IEEE802_3,
                                           dst=self.H[6],
                                           src=self.H[2]))

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        while True:
            self.cc_cnt2 += 1
            match = parser.OFPMatch(in_port=1, eth_type=0x05dc, eth_dst=self.H[6])
            actions = [parser.OFPActionOutput(3)]
            inst = parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
            self.add_flow(datapath, 1000, match, 0, [inst])
            pkt.serialize()
            out = parser.OFPPacketOut(datapath=datapath,
                                      buffer_id=ofproto.OFP_NO_BUFFER,
                                      in_port=1,
                                      actions=actions, data=pkt.data)
            datapath.send_msg(out)
            self.logger.info("%f : %s번 째 C&C2 generated in switch%s " % (time.time(), self.cc_cnt2, datapath.id))
            df = pd.DataFrame([(datapath.id, 1, self.cc_cnt2, time.time(), 'x')],
                              columns=['switch', 'class', 'number', 'time', 'queue'])
            self.generated_log = self.generated_log.append(df)
            hub.sleep(self.cc_period / 1000)

            if (self.cc_cnt2 >= self.command_control):
                self.terminal += 1
                if self.terminal == 6:
                    self.generated_log.to_csv('switchlog0818_generated.csv')
                break

    def _ad_gen1(self):
        hub.sleep(3)
        datapath = self.dp[1]
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_8021AD,
                                           dst=self.H[4],
                                           src=self.H[0]))

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        while True:
            self.ad_cnt += 1
            #match = parser.OFPMatch(in_port=1, eth_type=0x88a8, eth_dst=self.H[4])
            actions = [parser.OFPActionOutput(3)]
            #inst = parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
            #self.add_flow(datapath, 1000, match, 0, [inst])
            pkt.serialize()
            out = parser.OFPPacketOut(datapath=datapath,
                                      buffer_id=ofproto.OFP_NO_BUFFER,
                                      in_port=1,
                                      actions=actions, data=pkt.data)
            datapath.send_msg(out)
            self.logger.info("%f : %s번 째 Audio1 generated in switch%s " % (time.time(), self.ad_cnt, datapath.id))
            df = pd.DataFrame([(datapath.id, 2, self.ad_cnt, time.time(), 'x')],
                              columns=['switch', 'class', 'number', 'time', 'queue'])
            self.generated_log = self.generated_log.append(df)
            hub.sleep(self.ad_period / 1000)

            if (self.ad_cnt >= self.audio):
                self.terminal += 1
                break

    def _ad_gen2(self):
        hub.sleep(3)
        datapath = self.dp[2]
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_8021AD,
                                           dst=self.H[7],
                                           src=self.H[3]))

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        while True:
            self.ad_cnt2 += 1
            match = parser.OFPMatch(in_port=2, eth_type=0x88a8, eth_dst=self.H[7])
            actions = [parser.OFPActionOutput(3)]
            inst = parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
            self.add_flow(datapath, 1000, match, 0, [inst])
            pkt.serialize()
            out = parser.OFPPacketOut(datapath=datapath,
                                      buffer_id=ofproto.OFP_NO_BUFFER,
                                      in_port=2,
                                      actions=actions, data=pkt.data)
            datapath.send_msg(out)
            self.logger.info("%f : %s번 째 Audio2 generated in switch%s " % (time.time(), self.ad_cnt2, datapath.id))
            df = pd.DataFrame([(datapath.id, 2, self.ad_cnt2, time.time(), 'x')],
                              columns=['switch', 'class', 'number', 'time', 'queue'])
            self.generated_log = self.generated_log.append(df)
            hub.sleep(self.ad_period / 1000)

            if (self.ad_cnt2 >= self.audio):
                self.terminal += 1
                break

    def _vd_gen1(self):
        hub.sleep(3)
        datapath = self.dp[1]
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_8021AH,
                                           dst=self.H[4],
                                           src=self.H[0]))

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        while True:
            self.vd_cnt += 1
            match = parser.OFPMatch(in_port=1, eth_type=0x88e7, eth_dst=self.H[4])
            actions = [parser.OFPActionOutput(3)]
            inst = parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
            self.add_flow(datapath, 1000, match, 0, [inst])
            pkt.serialize()
            out = parser.OFPPacketOut(datapath=datapath,
                                      buffer_id=ofproto.OFP_NO_BUFFER,
                                      in_port=1,
                                      actions=actions, data=pkt.data)
            datapath.send_msg(out)
            self.logger.info("%f : %s번 째 Video1 generated in switch%s " % (time.time(), self.vd_cnt, datapath.id))
            df = pd.DataFrame([(datapath.id, 3, self.vd_cnt, time.time(), 'x')],
                              columns=['switch', 'class', 'number', 'time', 'queue'])
            self.generated_log = self.generated_log.append(df)
            hub.sleep(self.vd_period / 1000)

            if (self.vd_cnt >= self.video):
                self.terminal += 1
                break

    def _vd_gen2(self):
        hub.sleep(3)
        datapath = self.dp[2]
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_8021AH,
                                           dst=self.H[7],
                                           src=self.H[3]))

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        while True:
            self.vd_cnt2 += 1
            match = parser.OFPMatch(in_port=2, eth_type=0x88e7, eth_dst=self.H[7])
            actions = [parser.OFPActionOutput(3)]
            inst = parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
            self.add_flow(datapath, 1000, match, 0, [inst])
            pkt.serialize()
            out = parser.OFPPacketOut(datapath=datapath,
                                      buffer_id=ofproto.OFP_NO_BUFFER,
                                      in_port=2,
                                      actions=actions, data=pkt.data)
            datapath.send_msg(out)
            self.logger.info("%f : %s번 째 Video2 generated in switch%s " % (time.time(), self.vd_cnt2, datapath.id))
            df = pd.DataFrame([(datapath.id, 3, self.vd_cnt2, time.time(), 'x')],
                              columns=['switch', 'class', 'number', 'time', 'queue'])
            self.generated_log = self.generated_log.append(df)
            hub.sleep(self.vd_period / 1000)

            if (self.vd_cnt2 >= self.video):
                self.terminal += 1
                break


    #
    # def _vd_gen2(self):
    #     datapath = self.dp[2]
    #     pkt = packet.Packet()
    #     pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_8021AH,
    #                                        dst=self.H[7],
    #                                        src=self.H[3]))
    #
    #     ofproto = datapath.ofproto
    #     parser = datapath.ofproto_parser
    #     pkt.serialize()
    #
    #     match = parser.OFPMatch(in_port=2, eth_dst=self.H[7])
    #     actions = [parser.OFPActionOutput(3)]
    #     self.add_flow(datapath, 1, match, actions, ofproto.OFP_NO_BUFFER)
    #     match = parser.OFPMatch(in_port=2)
    #     data = pkt.data
    #
    #     out = parser.OFPPacketOut(datapath=datapath,
    #                               buffer_id=ofproto.OFP_NO_BUFFER,
    #                               match=match,
    #                               actions=actions, data=data)
    #     while True:
    #         self.vd_cnt2 += 1
    #         datapath.send_msg(out)
    #         self.logger.info("%f : video2 generated %s, 스위치%s " % (time.time(), self.vd_cnt2, datapath.id))
    #
    #         df = pd.DataFrame([(datapath.id, 3, self.vd_cnt2, time.time(), 'x')],
    #                           columns=['switch', 'class', 'number', 'time', 'queue'])
    #         self.generated_log = self.generated_log.append(df)
    #         hub.sleep(self.vd_period / 1000)
    #         if (self.vd_cnt2 >= self.video):
    #             self.terminal+=1
    #             break
                # if (self.cc_cnt >= self.command_control) and (self.cc_cnt2 >= self.command_control) and (self.ad_cnt >= self.audio) \
                #         and (self.ad_cnt2 >= self.audio) and (self.vd_cnt >= self.video):
                #     self.terminal=True
                #     break

            #
            # if (self.cc_cnt >= self.command_control) and (self.cc_cnt2 >= self.command_control) and (
            #         self.ad_cnt >= self.audio) \
            #         and (self.ad_cnt2 >= self.audio) and (self.vd_cnt >= self.video) and (self.vd_cnt2 >= self.video):
            #     self.terminal = True
            #     break
