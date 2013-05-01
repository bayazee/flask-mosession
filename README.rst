flask-mosession
===============

Alternative for Flask session module that uses MongoDB as main storage


Easy to setup and use
=====================

Here is an example showing how to setup and use flask-mosession:

.. code-block:: python

    from datetime import datetime
    from flask import Flask, session
    from flask.ext.mosession import MoSessionExtension
    
    app = Flask(__name__)
    
    app.config['MONGODB_HOST'] = '127.0.0.1'
    app.config['MONGODB_PORT'] = 27017
    app.config['MONGODB_DATABASE'] = 'session_test_db'
    mosession = MoSessionExtension(app)
    
    
    @app.route("/")
    def hello():
        if 'first_visit' not in session:
            session['first_visit'] = datetime.now()
    
        return 'Hi dear, your first visit was on ' + str(session['first_visit'])
    
    
    if __name__ == '__main__':
        app.run()
