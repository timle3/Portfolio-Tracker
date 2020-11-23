from flask import Flask, request, jsonify, Response, make_response, render_template
app = Flask(__name__)

from db import engine, Pageloads
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from sqlalchemy import func
import uuid

from pixel import PIXEL
from iphandle import get_company_from_request


# TODO: Input company name
@app.route('/addrow', methods=['POST', 'GET', 'HEAD'])
def insert():
    Session = sessionmaker(bind=engine)
    session = Session()

    page = 'NOT_DEFINED'
    if request.referrer:
        page = request.referrer

    company = get_company_from_request(request)
    new_uuid = uuid.uuid4().hex
    entry = Pageloads(id=new_uuid, timestamp=datetime.utcnow(), page_name=page, company=company)
    session.add(entry)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        print(e)
    finally:
        session.close()

    response = make_response(render_template('progress.js', id=new_uuid)) # need a path for the js template
    response.headers['Content-Type'] = 'text/javascript'
    return response


# query db and return list of pageloads
# can provide 2 optional arguments, start_date and end_date to specify date range
# if arguments are not provided:
#            end_date is set to current time
#            start_date is set to current time - 10 days
@app.route('/pageloads')
def get_pageloads_with_date():
    Session = sessionmaker(bind=engine)
    session = Session()

    # handle parsing datetime objects if present
    if 'start_date' and 'end_date' in request.args:

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        try:
            start_date_datetime = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            end_date_datetime = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')

        except Exception as e:
            return Response(status=400, response='Issue parsing timestamp arguments. Please double check formatting')
        finally:
            session.close()

    # if datetime parameters are not present, default range is 10 days
    else:
        start_date_datetime = datetime.utcnow() - timedelta(days=10)
        end_date_datetime = datetime.utcnow()

    records = session.query(Pageloads).filter(Pageloads.timestamp >= start_date_datetime,
                                              Pageloads.timestamp <= end_date_datetime).all()

    response_body = []

    # build response body
    for record in records:
        pageload_object = {}
        pageload_object['timestamp'] = record.timestamp
        pageload_object['page_name'] = record.page_name
        pageload_object['company'] = record.company
        response_body.append(pageload_object)

    session.close()
    return jsonify(response_body)


@app.route('/pageloads_per_company')
def get_pageloads_per_company():
    """ returns a json file containing:
         {
         ( 'company', [# of hits, % of page_ends]), ...
         }
    """

    Session = sessionmaker(bind=engine)
    session = Session()

    if 'start_date' and 'end_date' in request.args:

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        try:
            start_date_datetime = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            end_date_datetime = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')

        except Exception as e:
            return Response(status=400, response='Issue parsing timestamp arguments. Please double check formatting')
        finally:
            session.close()

    # if datetime parameters are not present, default range is 10 days
    else:
        start_date_datetime = datetime.utcnow() - timedelta(days=10)
        end_date_datetime = datetime.utcnow()

    record = session.query(
            func.count(Pageloads.company),
            Pageloads.company,
            func.count(Pageloads.page_end)
        ).group_by(Pageloads.company).filter(
        Pageloads.timestamp >= start_date_datetime,
        Pageloads.timestamp <= end_date_datetime).all()

    response_body = {}

    for r in record:
        #     company name  = count
        if r[1]:
            page_end_percent = 0
            if r[2]:
                page_end_percent = r[2] / r[0]
            response_body[r[1]] = [r[0], page_end_percent]

    # first query does not count null values so a separate query is done
    record = session.query(
            func.count("*"),
            func.count(Pageloads.page_end)
        ).filter(Pageloads.timestamp >= start_date_datetime,
                                                   Pageloads.timestamp <= end_date_datetime,
                                                   Pageloads.company == None).all()
    
    if record[0][0] is not None:
        if record[0][0] != 0:
            page_end_percent = 0
            if record[0][1]:
                page_end_percent = record[0][1] / record[0][0]
            response_body["Unknown"] = [record[0][0], page_end_percent]
    else:
        raise Exception("Issue counting null values in db")

    session.close()
    return jsonify(response_body)


if __name__ == '__main__':
    app.run(debug=True)
