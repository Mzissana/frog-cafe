from fastapi import APIRouter, Depends, HTTPException, status
from src.db import get_db_connection
from src.schemas import Order, OrderCreate, OrderStatusUpdate
from src.dependencies import get_current_user, require_role
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/", response_model=list[Order])
def get_orders(current_user=Depends(get_current_user)):
    logger.info(f"GET /orders requested by user {current_user['user_id']}")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT o.id, o.created_at, s.name as status
            FROM public.orders o
            JOIN public.order_statuses s ON o.status_id = s.id
            ORDER BY o.created_at DESC;
        """)
        orders = cur.fetchall()
        logger.info(f"Fetched {len(orders)} orders")

        for order in orders:
            cur.execute("""
                SELECT m.id, m.dish_name, m.image, m.is_available, m.description,
                       m.category, m.quantity_left, COUNT(*) as quantity
                FROM public.cart c
                JOIN public.menu m ON c.menu_item = m.id
                WHERE c.order_id = %s
                GROUP BY m.id, m.dish_name, m.image, m.is_available, 
                         m.description, m.category, m.quantity_left;
            """, (order["id"],))
            items = cur.fetchall()
            order["items"] = items or []
            logger.debug(f"Order {order['id']} has {len(order['items'])} items")

        return orders

    except Exception as e:
        logger.error(f"Error in get_orders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении заказов: {str(e)}")
    finally:
        cur.close()
        conn.close()


@router.post("/", response_model=Order, status_code=status.HTTP_201_CREATED)
def create_order(current_user=Depends(get_current_user)):
    logger.info(f"POST /orders by user {current_user['user_id']}")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN;")

        cur.execute("""
            SELECT id FROM public.toads 
            WHERE is_taken = false 
            ORDER BY id 
            LIMIT 1 
            FOR UPDATE;
        """)
        toad = cur.fetchone()
        toad_id = toad["id"] if toad else None
        logger.info(f"Toad selected: {toad_id}")

        if toad:
            cur.execute("UPDATE public.toads SET is_taken = true WHERE id = %s;", (toad_id,))
            logger.info(f"Toad {toad_id} marked as taken")

        cur.execute("""
            SELECT id, name 
            FROM public.order_statuses 
            WHERE name = 'Создан' 
            LIMIT 1;
        """)
        status = cur.fetchone()
        if not status:
            logger.error("Initial status 'Создан' not found")
            raise HTTPException(status_code=500, detail="Не удалось найти начальный статус заказа")

        logger.info(f"Status selected: {status['id']} ({status['name']})")

        cur.execute("""
            INSERT INTO public.orders (user_id, toad_id, status_id)
            VALUES (%s, %s, %s)
            RETURNING id, created_at;
        """, (current_user["user_id"], toad_id, status["id"]))
        new_order = cur.fetchone()

        if not new_order:
            logger.error("Failed to insert new order")
            raise HTTPException(status_code=500, detail="Не удалось создать заказ")

        logger.info(f"Order created with ID {new_order['id']} at {new_order['created_at']}")
        conn.commit()

        return {
            "id": new_order["id"],
            "created_at": new_order["created_at"],
            "status": status["name"],
            "items": []
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании заказа: {str(e)}")
    finally:
        cur.close()
        conn.close()


@router.get("/{order_id}", response_model=Order)
def get_order(order_id: int, current_user=Depends(get_current_user)):
    logger.info(f"GET /orders/{order_id} by user {current_user['user_id']}")
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM public.orders WHERE id = %s;", (order_id,))
    order = cur.fetchone()
    cur.close()
    conn.close()

    if not order:
        logger.warning(f"Order {order_id} not found")
        raise HTTPException(status_code=404, detail="Заказ не найден")

    if current_user["role_id"] != 0 and order["user_id"] != current_user["user_id"]:
        logger.warning(f"User {current_user['user_id']} unauthorized to access order {order_id}")
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    logger.info(f"Order {order_id} returned to user {current_user['user_id']}")
    return order


@router.put("/{order_id}/status", response_model=Order)
def update_order_status(order_id: int, update: OrderStatusUpdate, current_user=Depends(get_current_user)):
    logger.info(f"PUT /orders/{order_id}/status by user {current_user['user_id']}")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT id, status_id FROM public.orders WHERE id = %s;", (order_id,))
        order = cur.fetchone()
        if not order:
            logger.warning(f"Order {order_id} not found")
            raise HTTPException(status_code=404, detail="Заказ не найден")

        cur.execute("""
            UPDATE public.orders
            SET status_id = %s
            WHERE id = %s
            RETURNING id, created_at;
        """, (update.status_id, order_id))
        updated = cur.fetchone()

        if not updated:
            logger.error(f"Failed to update order {order_id}")
            raise HTTPException(status_code=500, detail="Не удалось обновить статус заказа")

        cur.execute("SELECT name FROM public.order_statuses WHERE id = %s;", (update.status_id,))
        status = cur.fetchone()

        cur.execute("""
            SELECT m.id, m.dish_name, m.image, m.is_available, m.description,
                   m.category, m.quantity_left, COUNT(*) as quantity
            FROM public.cart c
            JOIN public.menu m ON c.menu_item = m.id
            WHERE c.order_id = %s
            GROUP BY m.id, m.dish_name, m.image, m.is_available, 
                     m.description, m.category, m.quantity_left;
        """, (order_id,))
        items = cur.fetchall()
        conn.commit()

        logger.info(f"Order {order_id} status updated to {status['name']}")

        return {
            "id": updated["id"],
            "created_at": updated["created_at"],
            "status": status["name"],
            "items": items or []
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Error updating order status: {str(e)}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении статуса заказа: {str(e)}")
    finally:
        cur.close()
        conn.close()


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, current_user=Depends(get_current_user)):
    logger.info(f"DELETE /orders/{order_id} by user {current_user['user_id']}")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT o.id, o.toad_id, s.name as status
            FROM public.orders o
            JOIN public.order_statuses s ON o.status_id = s.id
            WHERE o.id = %s;
        """, (order_id,))
        order = cur.fetchone()

        if not order:
            logger.warning(f"Order {order_id} not found")
            raise HTTPException(status_code=404, detail="Заказ не найден")

        if order["status"] != "Выдан":
            logger.warning(f"Order {order_id} cannot be deleted - status is {order['status']}")
            raise HTTPException(status_code=400, detail="Можно удалить только заказы со статусом 'Выдан'")

        if order["toad_id"]:
            cur.execute("UPDATE public.toads SET is_taken = false WHERE id = %s;", (order["toad_id"],))
            logger.info(f"Toad {order['toad_id']} released")

        cur.execute("DELETE FROM public.cart WHERE order_id = %s;", (order_id,))
        cur.execute("DELETE FROM public.orders WHERE id = %s RETURNING id;", (order_id,))
        deleted = cur.fetchone()

        if not deleted:
            logger.error(f"Failed to delete order {order_id}")
            raise HTTPException(status_code=500, detail="Не удалось удалить заказ")

        conn.commit()
        logger.info(f"Order {order_id} deleted")
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Error deleting order {order_id}: {str(e)}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении заказа: {str(e)}")
    finally:
        cur.close()
        conn.close()


@router.delete("/", status_code=204, dependencies=[Depends(get_current_user)])
def clear_orders():
    logger.info("DELETE /orders — clearing all orders and cart")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN;")
        cur.execute("DELETE FROM public.cart;")
        cur.execute("DELETE FROM public.orders;")
        conn.commit()
        logger.info("All orders and cart items deleted")
    except Exception as e:
        logger.error(f"Error clearing orders: {str(e)}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при очистке заказов: {str(e)}")
    finally:
        cur.close()
        conn.close()
