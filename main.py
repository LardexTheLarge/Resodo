import sys
import asyncio
import uvicorn
from fastapi import FastAPI
from routers.contact import router as contact_router

app = FastAPI(title='Resodo - AI Web Scraper for Contact Info and Legal Documents')

app.include_router(contact_router)

@app.get('/')
async def root():
    return {'message': 'ALL SYSTEMS ONLINE', 'status': 'running'}

class ProactorServer(uvicorn.Server):
    def run(self, sockets=None):
        if sys.platform == 'win32':
            print('Setting ProactorEventLoopPolicy for Uvicorn Server')
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(self.serve(sockets=sockets))

if __name__ == '__main__':
    config = uvicorn.Config(
        'main:app',
        host='0.0.0.0',
        port=8000,
        reload=False,
        log_level='info'
    )
    
    server = ProactorServer(config=config)
    server.run()