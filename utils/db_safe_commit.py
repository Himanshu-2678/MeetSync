import time

def safe_commit(db, logger=None, retries=3):
    for attempt in range(retries):
        try:
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            if logger:
                logger.warning(f"DB commit failed (attempt {attempt+1}): {e}")
            time.sleep(1)

    if logger:
        logger.error("DB commit permanently failed")
    return False