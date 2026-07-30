import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Initialize the FastAPI application
app = FastAPI(title="Depop Scraper API")

# Configure Cross-Origin Resource Sharing. TODO: CHANGE AFTER DEPLOYMENT!!
# Currently set so that any frontend can access this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (safe for local development)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the expected structure of the POST request from Figma
class ScrapeRequest(BaseModel):
    query: str

# Trigger Endpoint (POST)
@app.post("/api/scrape")
def start_scrape(request: ScrapeRequest):
    # TODO: Replace this logic with Celery trigger:
    # task = run_pipeline_task.delay(request.query)
    # return {"task_id": task.id}

    # Returning a fake task ID to test the frontend workflow
    mock_task_id = f"task_123"
    
    return {
        "status": "Task accepted",
        "task_id": mock_task_id,
        "message": f"Started background scraping for: {request.query}"
    }

# Results Endpoint (GET)
@app.get("/api/results/{task_id}")
def get_results(task_id: str):
    # Connect to your local database
    try:
        conn = sqlite3.connect("depop_data.db")
        
        # Returns query results as dictionary INSTEAD of tuple
        # Easier to convert them to JSON later, since can call index and key 
        # conn.row_factory is setting in database library to control how query results are returned.
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                l.listing_id, 
                l.title, 
                l.price, 
                s.username as seller_name
            FROM listings l
            LEFT JOIN sellers s ON l.seller_id = s.seller_id
            LIMIT 50
        """)
        
        rows = cursor.fetchall()
        conn.close()

        # Convert the SQLite Row objects into standard Python dictionaries
        results = [dict(row) for row in rows]

        # FastAPI automatically converts this dictionary return into a JSON response
        return {
            "task_id": task_id,
            "status": "SUCCESS",
            "count": len(results),
            "data": results
        }

    except sqlite3.Error as e:
        # If the database doesn't exist or the query fails, return a 500 Error
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")