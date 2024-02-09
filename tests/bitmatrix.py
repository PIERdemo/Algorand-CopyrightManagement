from beaker import localnet, client
from src.bitmatrix.application import app, get_right
from algosdk import transaction
from algosdk.atomic_transaction_composer import AtomicTransactionComposer, TransactionWithSigner, LogicSigTransactionSigner

get_min_balance = lambda address: algo_client.account_info(address)['min-balance']

if __name__ == "__main__":
    algo_client = localnet.get_algod_client()
    build_app = app.build()
    build_app.export("./artifacts/bitmatrix")

    accounts = localnet.kmd.get_accounts()
    user_1 = accounts[0]
    user_2 = accounts[1]

    ###### TEST #########
    user_1mb_before = get_min_balance(user_1.address)
    user_2mb_before = get_min_balance(user_2.address)

    """
    TODO: Cambiare tutto sullo user_2
    TODO: Con la prepare, per decoupulare  chi create da chi lo usa
    TODO: Misurare anche lo SC
    """

    user1_app_client = client.ApplicationClient(
                    client=localnet.get_algod_client(),
                    app=app,
                    sender=user_1.address,
                    signer=user_1.signer,
                )
    app_id, addr, txid = user1_app_client.create()
    #####################

    user_2_app_client = user1_app_client.prepare(signer = user_2.signer)
    user_2_app_client.opt_in()

    #FUND STATEFUL SMART CONTRACT
    fund_transaction = transaction.PaymentTxn(sp= algo_client.suggested_params(), sender=user_2.address, receiver=addr, amt=1000000)
    tx_id = algo_client.send_transaction(fund_transaction.sign(user_2.private_key))
    transaction.wait_for_confirmation(algo_client, tx_id, 10)


    # CREATE TRANSACTION FOR THE ASA
    asa_tx = transaction.AssetConfigTxn(sp=algo_client.suggested_params(),
                                        sender=user_2.address,
                                        total=10_000,
                                        default_frozen=False,
                                        unit_name="GloC-Net",
                                        asset_name="IPI_NUM;NAME",
                                        manager=user_2.address,
                                        reserve=user_2.address,
                                        freeze=user_2.address,
                                        clawback=user_2.address,
                                        url="cc;ro;ri",
                                        decimals=2
                                    )

    # CREATE THE ATOMIC TRANSACTION COMPOSER AND ADD THE TRANSACTION
    atomic_tx_composer = AtomicTransactionComposer()
    atomic_tx_composer.add_method_call(sp = algo_client.suggested_params(),
                                       app_id = app_id,
                                       method =  build_app.contract.get_method_by_name("set_right"),
                                       sender =  user_2.address,
                                       signer= user_2.signer,
                                       method_args = [7, 1])
    atomic_tx_composer.add_transaction(TransactionWithSigner(asa_tx, user_2.signer))
    results = atomic_tx_composer.execute(algo_client,10)

    ###### TEST #########
    user_1mb_after = get_min_balance(user_1.address)
    user_2mb_after = get_min_balance(user_2.address)

    mb_user_1, mb_user_2 = user_1mb_after-user_1mb_before, user_2mb_after-user_2mb_before
    print(f"User 1: {mb_user_1}\nUser 2: {mb_user_2}")
    #####################