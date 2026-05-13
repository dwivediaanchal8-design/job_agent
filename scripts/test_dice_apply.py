import uuid
from backend.tasks.job_tasks import run_job_agent

def test_dice_apply():
    user_id = "fed31086-c7ba-4259-adb7-b732b36586fb"
    portal = "dice"
    
    print(f"Starting LIVE Dice Apply Test for user {user_id}...")
    
    try:
        # Since this script is NOT async, run_job_agent can use asyncio.run() internally
        # We need a MockTask for the 'self' argument
        class MockTask:
            def update_state(self, *args, **kwargs): pass
        
        # Call the raw function
        result = run_job_agent.run(user_id=user_id, portal=portal, dry_run=False)
        print("\nTest Result:")
        print(result)
    except Exception as e:
        print(f"\nTest Failed: {e}")

if __name__ == "__main__":
    test_dice_apply()
