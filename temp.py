from sqlalchemy import create_engine, text
engine = create_engine('postgresql://postgres:Aanchal%4027@localhost:5432/job_agent_db')
with engine.connect() as conn:
    conn.execute(text("UPDATE job_preferences SET keywords = ARRAY['Software Developer Intern'] WHERE user_id = 'fed31086-c7ba-4259-adb7-b732b36586fb'"))
    conn.commit()
