from beaker import localnet, client
from src.bitmatrix.application import app, get_right, set_right
from algosdk import transaction
from algosdk.atomic_transaction_composer import AtomicTransactionComposer, TransactionWithSigner, LogicSigTransactionSigner



if __name__ == "__main__":
    algo_client = localnet.get_algod_client()
    build_app = app.build()
    build_app.export("./artifacts/bitmatrix")

    accounts = localnet.kmd.get_accounts()
    user = accounts[0]

    app_client = client.ApplicationClient(
                    client=localnet.get_algod_client(),
                    app=app,
                    sender=user.address,
                    signer=user.signer,
                )
    
    app_id, addr, txid = app_client.create()
    app_client.opt_in()

    RIGHTS_TO_GET = [7, 15]
    for right in RIGHTS_TO_GET:
        result = app_client.call(get_right, index = right)
        print(f"Right at index {right}: {result.return_value}")


    #FUND STATEFUL SMART CONTRACT
    fund_transaction = transaction.PaymentTxn(sp= algo_client.suggested_params(), sender=user.address, receiver=addr, amt=1000000)
    tx_id = algo_client.send_transaction(fund_transaction.sign(user.private_key))
    transaction.wait_for_confirmation(algo_client, tx_id, 10)


    # CREATE TRANSACTION FOR THE ASA
    asa_tx = transaction.AssetConfigTxn(sp=algo_client.suggested_params(),
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

    # CREATE THE ATOMIC TRANSACTION COMPOSER AND ADD THE TRANSACTION
    atomic_tx_composer = AtomicTransactionComposer()
    atomic_tx_composer.add_method_call(sp = algo_client.suggested_params(),
                                       app_id = app_id,
                                       method =  build_app.contract.get_method_by_name("set_right"),
                                       sender =  user.address,
                                       signer= user.signer,
                                       method_args = [7, 1])
    atomic_tx_composer.add_transaction(TransactionWithSigner(asa_tx, user.signer))
    results = atomic_tx_composer.execute(algo_client,10)

    # GET THE RIGHTS
    print("=~"*20)
    for right in RIGHTS_TO_GET:
        result = app_client.call(get_right, index = right)
        print(f"Right at index {right}: {result.return_value}")