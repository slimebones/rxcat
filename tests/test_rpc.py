import asyncio

from pydantic import BaseModel
from pykit.code import get_fqname
from pykit.err import ValErr
from pykit.res import Err, Ok, Res
from pykit.uuid import uuid4

from rxcat import ConnArgs, ServerBus
from tests.conftest import (
    MockConn,
    find_datacodeid_in_welcome_rmsg,
    find_errcodeid_in_welcome_rmsg,
)


async def test_main(server_bus: ServerBus):
    class UpdateEmailArgs(BaseModel):
        username: str
        email: str
    async def srpc__update_email(args: UpdateEmailArgs) -> Res[int]:
        username = args.username
        email = args.email
        if username == "throw":
            return Err(ValErr("hello"))
        assert username == "test_username"
        assert email == "test_email"
        return Ok(0)

    conn_1 = MockConn(ConnArgs(
        core=None))
    conn_task_1 = asyncio.create_task(server_bus.conn(conn_1))

    welcome_rmsg = await asyncio.wait_for(conn_1.client__recv(), 1)
    rxcat_rpc_req_datacodeid = find_datacodeid_in_welcome_rmsg(
        "rxcat__srpc_send", welcome_rmsg).eject()

    ServerBus.reg_rpc(srpc__update_email).eject()

    rpc_token = uuid4()
    rpc_key = "srpc__update_email:" + rpc_token
    await conn_1.client__send({
        "sid": uuid4(),
        "datacodeid": rxcat_rpc_req_datacodeid,
        "data": {
            "key": rpc_key,
            "args": {"username": "test_username", "email": "test_email"}
        }
    })
    rpc_recv = await asyncio.wait_for(conn_1.client__recv(), 1)
    rpc_data = rpc_recv["data"]
    assert rpc_data["key"] == rpc_key
    assert rpc_data["val"] == 0

    rpc_token = uuid4()
    rpc_key = "srpc__update_email:" + rpc_token
    await conn_1.client__send({
        "sid": uuid4(),
        "datacodeid": rxcat_rpc_req_datacodeid,
        "data": {
            "key": rpc_key,
            "args": {"username": "throw", "email": "test_email"}
        }
    })
    rpc_recv = await asyncio.wait_for(conn_1.client__recv(), 1)
    rpc_data = rpc_recv["data"]
    assert rpc_data["key"] == rpc_key
    val = rpc_data["val"]
    assert val["datacodeid"] == \
        find_errcodeid_in_welcome_rmsg("val-err", welcome_rmsg).eject()
    assert val["msg"] == "hello"
    assert val["name"] == get_fqname(ValErr())

    conn_task_1.cancel()
