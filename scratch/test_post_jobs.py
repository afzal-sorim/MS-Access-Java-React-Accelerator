import sys
import asyncio
from pathlib import Path

sys.path.insert(0, r"c:\Users\Admin.ST-SHANKAR\Downloads\MS-Access-Java-React-Accelerator-base-working (2)\MS-Access-Java-React-Accelerator-base-working")

from converter.app.database import init_database, get_session, JobRepository, JobModel
from converter.app.api.auth.mongo_db import MongoUser

async def test_job_creation():
    await init_database()
    async with get_session() as session:
        user_id = "test-user-123"
        job = JobModel(
            id="testjob1",
            user_id=user_id,
            source_file="test.accdb",
            project_name="TestProject",
            base_package="com.test.app"
        )
        session.add(job)
        try:
            await session.commit()
            print("Successfully committed job with user_id:", user_id)
        except Exception as e:
            print("FAILED to commit job:", e)
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(test_job_creation())
