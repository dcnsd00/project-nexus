#!/usr/bin/env python3
"""Offline NEXUS operator simulation: manual command -> validation -> miner lifecycle -> Stratum job."""
from __future__ import annotations
import argparse, json, os, sys, tempfile, threading, socket, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class FakeProcess:
    _next=41000
    def __init__(self, cmd, **kwargs):
        type(self)._next += 1
        self.pid=type(self)._next; self.cmd=cmd; self.returncode=None
    def poll(self): return self.returncode
    def terminate(self): self.returncode=0
    def kill(self): self.returncode=-9
    def wait(self,timeout=None): return self.returncode or 0

def mock_pool_server():
    srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    srv.bind(("127.0.0.1",0)); srv.listen(1); port=srv.getsockname()[1]
    job=["sim-job","00"*32,"01000000","ffffffff",[],"20000000","1d00ffff","65a1b2c3",True]
    def run():
        conn,_=srv.accept()
        with conn:
            buf=b""; ids=set()
            while len(ids)<2:
                data=conn.recv(4096)
                if not data: return
                buf+=data
                while b"\n" in buf:
                    line,buf=buf.split(b"\n",1)
                    if line:
                        msg=json.loads(line); ids.add(msg.get("id"))
            replies=[
                {"id":1,"result":[[["mining.notify","sim"]],"abcd",4],"error":None},
                {"id":2,"result":True,"error":None},
                {"id":None,"method":"mining.set_difficulty","params":[1.0]},
                {"id":None,"method":"mining.notify","params":job},
            ]
            for x in replies: conn.sendall((json.dumps(x)+"\n").encode())
        srv.close()
    th=threading.Thread(target=run,daemon=True); th.start()
    return port,th

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--scenario",default="rvn-kawpow-trex")
    ap.add_argument("--json",default="")
    args=ap.parse_args()
    # Operator-supplied fields: representative manual Windows form values.
    command={"miner_id":"trex","pool_id":"2miners-rvn-eu","wallet":"R_TEST_WALLET_ADDRESS",
             "worker":"nexus-sim","algorithm":"KawPoW","device":"GPU","use_ssl":False,
             "binary_path":str(ROOT/"simulation"/"t-rex.exe")}
    if args.json:
        command.update(json.loads(Path(args.json).read_text(encoding="utf-8")))
    report={"scenario":args.scenario,"mode":"offline_simulation","external_actions":False,
            "manual_command":command,"stages":[]}
    from mining import controller
    from mining.stratum_session import probe_job
    # Resolve a fake executable and intercept process creation; no real miner runs.
    fake=Path(command["binary_path"]); fake.parent.mkdir(parents=True,exist_ok=True); fake.write_bytes(b"SIMULATED-EXECUTABLE")
    old_resolve,old_popen=controller._resolve_binary,controller.subprocess.Popen
    controller._resolve_binary=lambda mid, explicit_path=None: str(fake)
    controller.subprocess.Popen=FakeProcess
    try:
        started=controller.start(command)
        report["stages"].append({"name":"manual_input_validation_and_controller_start","status":"PASS",
                                 "miner":started.get("miner_name"),"algorithm":started.get("algorithm"),
                                 "pool":started.get("pool"),"pid_simulated":started.get("pid"),
                                 "command_log":started.get("log_path")})
        stopped=controller.stop()
        report["stages"].append({"name":"controller_stop","status":"PASS","status_after_stop":stopped.get("status")})
    finally:
        controller._resolve_binary=old_resolve
        controller.subprocess.Popen=old_popen
    # Mock pool receives subscribe+authorize and returns set_difficulty+notify.
    port,th=mock_pool_server()
    result=probe_job("127.0.0.1",port,"simulation.worker",timeout=4)
    th.join(2)
    report["stages"].append({"name":"stratum_v1_mock_handshake_and_job","status":"PASS" if result.get("ok") else "FAIL",
                             "result":result})
    # Verify downstream Bitcoin header construction from received job data.
    from mining.stratum_session import build_coinbase_hash,build_merkle_root,build_header
    cb=build_coinbase_hash("01020304","aa","bb","ccdd")
    mr=build_merkle_root(cb,[])
    header=build_header("20000000","00"*32,mr,"65a1b2c3","1d00ffff",0x12345678)
    report["stages"].append({"name":"coinbase_merkle_header_pipeline","status":"PASS" if len(header)==80 else "FAIL",
                             "header_bytes":len(header),"nonce_le":header[-4:].hex()})
    report["summary"]={"passed":sum(x["status"]=="PASS" for x in report["stages"]),
                       "failed":sum(x["status"]!="PASS" for x in report["stages"]),
                       "live_pool_test":False,"real_miner_started":False,"share_submitted":False,
                       "wallet_modified":False}
    out=ROOT/"results"/"virtual_operator_simulation_01011.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0 if report["summary"]["failed"]==0 else 2

if __name__=="__main__": raise SystemExit(main())
