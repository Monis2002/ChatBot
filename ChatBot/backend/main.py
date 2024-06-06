from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import db_helper
import generic_helper


app=FastAPI()

inprogress_order = {}

@app.post("/")
async def handle_request(request: Request):
    payload=await request.json()

    intent=payload['queryResult']['intent']['displayName']
    parameters=payload["queryResult"]['parameters']
    output_contexts=payload['queryResult']['outputContexts']


    # _____WE CAN DO LIKE THIS ALSO, BUT MORE BETTER WAY_____
    # if intent=='track.order - context : ongoing-order':
    #     return track_order(parameters)
    # elif intent=='order.add  -context: ongoing-order':
    #     pass
    # elif intent=='order.complete - context: ongoing-order':
    #     pass

    session_id=generic_helper.extract_session_id(output_contexts[0]['name'])

    intent_handler_dict={
        'track.order - context : ongoing-order':track_order,
        'order.add  -context: ongoing-order':add_to_order,
        'order.complete - context: ongoing-order':complete_order,
        'order.remove -context: ongoing-order':remove_from_order,
        'new.order':new_order
    }

    return intent_handler_dict[intent](parameters,session_id)


def new_order(parameters:dict,session_id:str):
    if session_id  in inprogress_order:
        del inprogress_order[session_id]
    return JSONResponse(content={
            "fulfillmentText": 'Ok, starting a new order. You can say things like "I want two pizzas and one mango lassi". Make sure to specify a quantity for every food item! Also, we have only the following items on our menu: Pav Bhaji, Chole Bhature, Pizza, Mango Lassi, Masala Dosa, Biryani, Vada Pav, Rava Dosa, and Samosa.'
        })

def remove_from_order(parameters:dict,session_id:str):
    if session_id not in inprogress_order:
        fulfillment_text="I''m having a trouble finding your order. Sorry ! Can you place a new order.."
        return JSONResponse(content={
            "fulfillmentText": fulfillment_text
        })
    else:
        current_order=inprogress_order[session_id]
        food_items=parameters['food-item']

        removed_items=[]
        no_such_items=[]
        for item in food_items:
            if item not in current_order:
                no_such_items.append(item)
            else:
                removed_items.append(item)
                del current_order[item]

        if len(removed_items)>0:
            fulfillment_text=f'Removed {", ".join(removed_items)} from your order'
        if len(no_such_items)>0:
            fulfillment_text=f"Your current oder does not have {', '.join(no_such_items)}"

        if len(current_order.keys())==0:
            fulfillment_text +=" Your order is empty!"
        else:
            order_str=generic_helper.get_str_from_food_dict(current_order)
            fulfillment_text+=f' Here is what is left in your order {order_str}'

        return JSONResponse(content={
            "fulfillmentText": fulfillment_text
        })

def track_order(parameters:dict,session_id:str):
    order_id=int(parameters['number'])
    order_status=db_helper.get_order_status(order_id)
    if order_status:
        fulfillment_text=f"The order status for order_id : {order_id} is : {order_status}"
    else:
        fulfillment_text=f"No order found with order id : {order_id}"
    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })

def add_to_order(parameters:dict,session_id:str):
    qtys=parameters['number']
    food_items=parameters["food-item"]
    print(qtys,food_items)
    if len(qtys)!=len(food_items):
        fulfillment_text="Sorry I didn't understand: Can you specify food items and quantities clearly"
    else:
        new_food_dict=dict(zip(food_items,qtys))

        if session_id in inprogress_order:
            current_food_dict=inprogress_order[session_id]
            current_food_dict.update(new_food_dict)

        else:
            inprogress_order[session_id]=new_food_dict

        ordered_string=generic_helper.get_str_from_food_dict(inprogress_order[session_id])
        fulfillment_text=f"So far you have ordered {ordered_string} .Do you need anything else?"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })

def complete_order(parameters:dict,session_id:str):
    if session_id not in inprogress_order:
        fulfillment_text="I''m having a trouble finding your order. Sorry ! Can you place a new order.."
    else:
        order=inprogress_order[session_id]
        order_id=save_to_db(order)

        if order_id==-1:
            fulfillment_text = "I''m having a trouble finding your order. Sorry ! Can you place a new order.."
        else:
            order_total=db_helper.get_total_order_price(order_id)
            fulfillment_text=f"Awesome. We have placed your order.\n"\
                             f"Here is your order id # {order_id}.\n"\
                            f"Your order total is {order_total}.\nwhich you can pay at the time of delivery !!"

    del inprogress_order[session_id]

    return JSONResponse(content={
        "fulfillmentText":fulfillment_text
    })


def save_to_db(order:dict):
    next_order_id=db_helper.get_next_order_id()
    for food_item,qty in order.items():
        rcode=db_helper.insert_order_item(
            food_item,qty,next_order_id
        )

        if rcode==-1:
            return -1
    db_helper.insert_order_tracking(next_order_id,"in progress")
    return next_order_id