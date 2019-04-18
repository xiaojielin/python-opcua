import sys
sys.path.insert(0, "..")
import logging
import time
from opcua import Client, ua
from datetime import datetime


try:
    from IPython import embed
except ImportError:
    import code

    def embed():
        vars = globals()
        vars.update(locals())
        shell = code.InteractiveConsole(vars)
        shell.interact()



class SubHandler(object):

    """
    this is the default alert, known as the messaging alert.
    Subscription Handler. To receive events from server for a subscription
    data_change and event methods are called directly from receiving thread.
    Do not do expensive, slow or network operation there. Create another 
    thread if you need to do such a thing
    in the subscription, the handler is used as follows:
        self._handler.datachange_notification(data.node, item.Value.Value.Value, event_data)
        self._handler.event_notification(result)

        we could have different handlers, some (like this one) is for giving alerts, while the others are to collect
        data or do other things.

    """

    def datachange_notification(self, node, val, data):
        print("Python: New data change event", node, val)

    def event_notification(self, event):
        print("Python: New event", event)


class RecordHandler(SubHandler):
    """
    this is the record handler

    """
    def datachange_notification(self, node, val, data):
        record = ' '.join([str(datetime.now()), 'Python: New data change event', str(node), str(val), '\n'])
        with open(''.join(['workfile', datetime.now().strftime("%Y%n%d-%H%M%S"), '.txt']),'wr') as f:
            f.write(record)
    def event_notification(self, event):
        print("Python: New event", event)

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARN)
    #logger = logging.getLogger("KeepAlive")
    #logger.setLevel(logging.DEBUG)

    client = Client("opc.tcp://localhost:4842")
    # client = Client("opc.tcp://admin@localhost:4840/freeopcua/server/") #connect using a user
    try:
        client.connect()
        client.load_type_definitions()  # load definition of server specific structures/extension objects

        #warm-up Client has a few methods to get proxy to UA nodes that should always be in address space such as \
        #Root or Objects. this is less useful  to Apros. Because in Apros, root node is in namespace 0 while all the \
        #data we want is in namespace 2.
        root = client.get_root_node()
        print("Root node is: ", root)
        # Node objects have methods to read and write node attributes as well as browse or populate address space
        print("Children of root are: ", root.get_children())
        # in Apros, roos is divided into Objects, Types and Views. Simulation node, though in namespace 2, behind \
        # Objects node, is where we get the data.
        [objects, types, views] = root.get_children()
        # or we can just get the objects node.\
        # objects = client.get_objects_node()
        print("Objects node is: ", objects)


        # now we show how to get the data from one node through node id. node id is a excellent way of referencing \
        # without using the browse path (which tends to cause mutiple return values of node id)
        # 1st, getting our namespace idx, it should always be 2.
        # by tradition, namespace 2 is for Simulation data. namespace 0 is for server connection and other type
        #definitions. objects have identifier of 85. types of 86 and view of 87. the root is 84. however, the data
        # we want, it has no identifier.
        uri = "http://www.apros.fi/OPC_UA/"
        idx = client.get_namespace_index(uri)

        # 2nd, get a specific node knowing its node id
        #first, create the nodeid. plz ref to opcua/client/client.py:490 and opcua/ua/uatypes.py:287
        aprosVarLabel = 'COV01.VA12_LIQ_MASS_FLOW'
        aprosVarType = 'CONTROL_VALVE'
        glue = '!'
        nodeIdentifier = glue.join(['TYPES', aprosVarType[0], aprosVarType, aprosVarLabel])
        #nodeIdentifier = 'TYPES!A!ANALOG_SIGNAL!XA01'
        myNodeId = ua.NodeId(nodeIdentifier, idx)
        #the final format of NodeId looks like:
        #(ns=2;s=TYPES!A!ANALOG_SIGNAL!XA01)
        myVarNode = client.get_node(myNodeId)  # including its current value, old value and address
        #[myFullVarValueObj, _, _] = myVarNode.get_variables()  #get the full Value object from the node.
        myVarDataValueObj = myVarNode.get_data_value()  # get the DataValue object from  full Value object
        myValue = myVarDataValueObj.Value
        print(myValue)

        #liusibin model
        def lsb(input):
            output = input*1.1
            return output
        #
        newValue = lsb(myValue)

        #first try of write: write simple value
        #this fails due to the rejection from the server. maybe it is impossible to write single value to a subscription
        #myVarNode.set_value([0.5], ua.VariantType.Double, includeTime = False)
        newDataValueObj = myVarDataValueObj
        newDataValueObj = ua.DataValue(ua.Variant(newValue, ua.VariantType.Double))
        myVarNode.set_attribute(ua.AttributeIds.Value, newDataValueObj)
        #newDataValueObj.Value = 0.5
        #myVarNode.set_value(newDataValueObj)
        #myVarValueObj.set_value(0.5)

        #now try to write a OPC Command
        aprosOPC = 'OPC_INI.OPC_COMMAND'
        aprosOPCType = 'OPC'
        opcNodeIdentifier = "!".join(['TYPES', aprosOPCType[0], aprosOPCType, aprosOPC])
        myOPCNodeId = ua.NodeId(opcNodeIdentifier, idx)
        myOPCObj = client.get_node(myOPCNodeId)
        myOPCInput = 'do 30'  # run simulation for 30s
        # OPC command here is basically Apros console command.
        opcInputDataValueObj = ua.DataValue(ua.Variant(myOPCInput, ua.VariantType.String))
        myOPCObj.set_attribute(ua.AttributeIds.Value, opcInputDataValueObj)

        #StringNodeId(ns=2;s=TYPES!O!OPC!OPC_INI.OPC_COMMAND)
        #for data or properties
        #var.get_data_value() # get value of node as a DataValue object
        #var.get_value() # get value of node as a python builtin
        #var.set_value(ua.Variant([23], ua.VariantType.Int64)) #set node value using explicit data type
        #var.set_value(3.9) # set node value using implicit data type

        # alternative to method\
        # Now getting a control variables node using its browse path
        # this is more straightforward.
        # the followed paths are all relative path.
        myCmd = 'OPC_COMMAND'
        myCmdObj = 'OPC_INI'
        objPath = '0:Objects'
        simPath = '2:Simulation'
        typesPath = '2:TYPES'
        typesLetterPath = ':'.join(['2', myCmd[0]])
        opcTypePath = '2:OPC'
        myCmdObjPath = ':'.join(['2', myCmdObj])
        myCmdShortPath = ':'.join(['2', myCmd])
        myCmdBrowsepath = [objPath, simPath, typesPath, typesLetterPath, opcTypePath, myCmdObjPath, myCmdShortPath]
        myOPCcmd = root.get_child(myCmdBrowsepath)
        print("myOPCcmd is: ", myOPCcmd)
        if myOPCcmd == myOPCObj:
            print('{0} is equal to {1}'.format('myOPCcmd', 'myOPCObj'))


        #TODO Subscribe to the signal
        # now we try to set up subscription to this variable. remember, for data like signal, they are dynamci vars and \
        # should be taken care through subscription.
        # subscribing to a variable node
        messager = SubHandler()  #messaging handler
        sub_messager = client.create_subscription(500, messager)
        handle_messager = sub_messager.subscribe_data_change(myVarNode)
        recorder = RecordHandler()  #record handler
        sub_recorder = client.create_subscription(500, recorder)
        handle_recorder = sub_recorder.subscribe_data_change(myVarNode)
        time.sleep(0.1)

        # we can also subscribe to events from server
        sub_messager.subscribe_events()
        # sub.unsubscribe(handle)
        # sub.delete()

        # calling a method on server
        #res = obj.call_method("{}:multiply".format(idx), 3, "klk")
        #print("method result is: ", res)

        embed()
    finally:
        client.disconnect()
