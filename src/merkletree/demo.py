import base64
from algosdk.atomic_transaction_composer import AtomicTransactionComposer, TransactionWithSigner, LogicSigTransactionSigner
from algosdk import transaction
import beaker
from pyteal import *
from src.merkletree.application import  calculate_root, app, get_root

construct_path = lambda path: b''.join([(b'\x01' if node[0] else b'\x00') + bytes.fromhex(node[1]) for node in path])
to_hex = lambda x: ''.join(format(b, '02x') for b in x)

def create_stateless_program(logic, algo_client = beaker.localnet.get_algod_client()):
    teal_code = compileTeal(logic(), mode=Mode.Signature, version=5)
    compiled_logic = algo_client.compile(teal_code)

    return base64.b64decode(compiled_logic["result"])

if __name__ == "__main__":
    # DEFAULT PARAMETERS FOR LOCALNET
    algo_client = beaker.localnet.get_algod_client()
    client_parameters = algo_client.suggested_params()
    accounts = beaker.localnet.kmd.get_accounts()

    user = accounts[0]


    # INPUT FOR STATELESS SMART CONTRACT
    leaf = b'\x01'*28
    old_leaf = b'\x00'*28

    path = [(True, '3addfb141cd7c9c4c6543a82191a3707ac29c7a041217782e61d4d91c691aee8'), (True, '65c1d29e33004871b9b0ad210d82512f75d49c25514340330368633d013f1fb4'), (True, '6a4a94c594c8aa9f435e40249a201c3bc0a22806a9282ac3b686449db2376597'), (True, '4b342b31656a4576da51c1bed81fc545c13f948611873d5e55ec074b3477fefb'), (True, 'ab450217f89b367aee56944e8de4fc8e6f5bebfd7ec711a9f8bc7ae55e4c2d3e'), (True, 'd4e649e90c29116b180302a9557b9a07274804388491499594f8e06ad94601b1'), (True, '6c41e95666294aa18693f926b8dbd2439b75189b860fd373651f6995cf2729b1'), (True, '7400052eaa10112a59ab23c7d8067b2789909d8214c70445ee77263fc3a909f5'), (True, '9247a3fb4f09f08e3add61ba18567fb0386aa0160f46ff287480b9f5f5c0ea26'), (True, 'e0243456524cdc2acd83f89524dd4b9983f2f637503a63a83b9243e4c53b9a70'), (True, 'b550dbb4700d0b0cf704e02ceed53900f82b32f625ba71494a1417d11dbc4bce'), (True, '43066a691eac30958ef52928e4e18d68b4aa45bf393f159835c42e13702cca8f'), (True, 'fba23d1cfe8fde4030a014c9049d821e93bf27f2d56d0c7875ffab49680f5c61'), (True, 'a51bb72629f76a59ccc52e0aff1c827ab4709895150700014a803979367da4de')]
    root = 'a569813670998fd1778e514878ec9cd61e9a56287a09672aed4788ee26fc7de0'

    old_root = 'faafa827d1aff5eca20d0b4b3d8ae668e23b478342fe484910716223138cc0d1'

    DEFAULT_ROOT = old_root

    byte_path = construct_path(path)
    path_len = (len(path)).to_bytes(8, 'big')
    byte_root = bytes.fromhex(root)
    byte_old_root = bytes.fromhex(old_root) 
    BYTE_DEFAULT_ROOT = bytes.fromhex(DEFAULT_ROOT)

    # CREATE STATELESS SMART CONTRACT
    program = create_stateless_program(calculate_root)
    logicsign_account = transaction.LogicSigAccount(program,args=[leaf, old_leaf, byte_path, path_len, byte_root, byte_old_root])

    #print(f'Logic Signature Address: {logicsign_account.address()}')

    #FUND STATELESS SMART CONTRACT
    fund_transaction = transaction.PaymentTxn(sp= client_parameters, sender=user.address, receiver=logicsign_account.address(), amt=1000000)
    tx_id = algo_client.send_transaction(fund_transaction.sign(user.private_key)) 
    transaction.wait_for_confirmation(algo_client, tx_id, 10)

    
    # CREATE TRANSACTION FOR STATELESS SMART CONTRACT
    stateless_tx = transaction.PaymentTxn(sp= client_parameters, sender=logicsign_account.address(), 
                                          receiver=user.address, amt=0, note=bytes.fromhex(root+old_root))

    # BUILD AND CREATE STATEFULL SMART CONTRACT
    build_app = app.build()
    build_app.export("./artifacts/merkletree")

    app_client = beaker.client.ApplicationClient(
                client=algo_client,
                app=app,
                sender=user.address,
                signer=user.signer,
            )
    app_id, addr, txid = app_client.create(deafult_root = BYTE_DEFAULT_ROOT)

    app_client.opt_in()

    #FUND STATEFUL SMART CONTRACT
    fund_transaction = transaction.PaymentTxn(sp= client_parameters, sender=user.address, receiver=addr, amt=1000000)
    tx_id = algo_client.send_transaction(fund_transaction.sign(user.private_key))
    transaction.wait_for_confirmation(algo_client, tx_id, 10)

    # CREATE TRANSACTION FOR THE ASA
    asa_tx = transaction.AssetConfigTxn(sp=client_parameters,
                                        sender=user.address,
                                        total=10_000,
                                        default_frozen=False,
                                        unit_name="GloC-Net",
                                        asset_name="IPI_NUM;NAME",
                                        manager=user.address,
                                        reserve=user.address,
                                        freeze=user.address,
                                        clawback=user.address,
                                        url="cc;ro;ri",
                                        decimals=2
                                    )



    # START THE TEST
    for i in range (3):
        rv = app_client.call(get_root,index = i)
        print(f'Root at index {i} is {to_hex(rv.return_value)}')



    # CREATE THE ATOMIC TRANSACTION COMPOSER AND ADD THE TRANSACTION
    atomic_tx_composer = AtomicTransactionComposer()
    atomic_tx_composer.add_transaction(TransactionWithSigner(stateless_tx, LogicSigTransactionSigner(logicsign_account)))
    atomic_tx_composer.add_method_call(sp = client_parameters,
                                       app_id = app_id,
                                       method =  build_app.contract.get_method_by_name("set_root"),
                                       sender =  user.address,
                                       signer= user.signer,
                                       method_args = [0, byte_root])
    atomic_tx_composer.add_transaction(TransactionWithSigner(asa_tx, user.signer))
    results = atomic_tx_composer.execute(algo_client,10)

    print('~-'*20)
    for i in range (3):
        rv = app_client.call(get_root,index = i)
        print(f'Root at index {i} is {to_hex(rv.return_value)}')
