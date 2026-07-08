import time

def log_stage(stage, data=None):

    print("\n" + "="*50)

    print(f"STAGE: {stage}")

    if data:

        print("DATA:")

        print(data)

    print("TIME:", time.strftime("%H:%M:%S"))

    print("="*50 + "\n")