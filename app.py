from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
import json
from collections import defaultdict
import calendar # Added for month calculation

# Assuming you have an ml_model.py in the same directory
from ml_model import predict_category

app = Flask(__name__)
app.secret_key = 'your-secret-key-here' # IMPORTANT: Change this to a strong, unique secret key

# Initialize session data if not exists
@app.before_request
def initialize_session():
    if 'expenses' not in session:
        session['expenses'] = []

# Make utilities available in all templates
@app.context_processor
def inject_utilities():
    return {
        'datetime': datetime,
        'enumerate': enumerate,
        'len': len,
        'str': str,
        'float': float,
        'max': max,
        'min': min,
        'dict': dict,
        'list': list
    }

# Routes
@app.route('/')
def index():
    expenses = session.get('expenses', [])
    recent_expenses = sorted(expenses, key=lambda x: x['date'], reverse=True)[:5]
    
    # Calculate summary stats
    total = sum(exp['amount'] for exp in expenses)
    categories = {}
    for exp in expenses:
        categories[exp['category']] = categories.get(exp['category'], 0) + exp['amount']
    
    # Find max category for the template
    max_category = max(categories.items(), key=lambda x: x[1], default=(None, None))
    
    return render_template('index.html', 
                           expenses=recent_expenses,
                           total=total,
                           categories=categories,
                           max_category=max_category[0] if max_category[0] else 'N/A')

@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            description = request.form['description'].strip()
            category = request.form['category']
            payment_method = request.form['payment_method']
            date_str = request.form['date']
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if amount <= 0:
                flash('Amount must be positive', 'danger')
                return redirect(url_for('add_expense'))
            
            new_expense = {
                'id': len(session['expenses']) + 1,
                'amount': amount,
                'description': description,
                'category': category,
                'payment_method': payment_method,
                'date': date.isoformat()
            }
            
            # Append new expense to the session list
            session['expenses'] = session['expenses'] + [new_expense]
            session.modified = True # Mark session as modified
            
            flash('Expense added successfully!', 'success')
            return redirect(url_for('index'))
        
        except ValueError as e:
            flash(f'Invalid input: {e}. Please check your entries.', 'danger')
            return redirect(url_for('add_expense'))
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('add_expense.html', current_date=current_date)

@app.route('/analytics')
def analytics():
    expenses = session.get('expenses', [])
    
    # Prepare data for charts
    categories = defaultdict(float)
    monthly_data = defaultdict(float)
    
    for exp in expenses:
        # Category data
        categories[exp['category']] += exp['amount']
        
        # Monthly data
        month_year = datetime.strptime(exp['date'], '%Y-%m-%d').strftime('%Y-%m')
        monthly_data[month_year] += exp['amount']
    
    return render_template('analytics.html',
                           category_data=json.dumps(categories),
                           monthly_data=json.dumps(monthly_data))

@app.route('/predict_category', methods=['POST'])
def predict_category_route():
    description = request.json.get('description', '')
    if not description:
        return jsonify({'error': 'Description is required'}), 400
    
    try:
        category = predict_category(description)
        return jsonify({'category': category})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('404.html', error=str(e)), 500

# Routes for monthly analytics navigation
@app.route('/analytics/<year_month>')
def monthly_analytics(year_month):
    try:
        year, month = map(int, year_month.split('-'))
        start_date = datetime(year, month, 1)
        # Calculate end date for the month
        _, num_days = calendar.monthrange(year, month)
        end_date = datetime(year, month, num_days, 23, 59, 59) # End of the month
    except ValueError:
        flash('Invalid month format', 'danger')
        return redirect(url_for('analytics'))
    
    monthly_expenses = []
    for exp in session.get('expenses', []):
        exp_date = datetime.strptime(exp['date'], '%Y-%m-%d')
        if start_date <= exp_date <= end_date: # Include expenses up to the end of the month
            monthly_expenses.append(exp)
    
    # Prepare data for charts
    categories = defaultdict(float)
    daily_data = defaultdict(float)
    
    for exp in monthly_expenses:
        categories[exp['category']] += exp['amount']
        exp_date_obj = datetime.strptime(exp['date'], '%Y-%m-%d') # Re-parse to get datetime object
        daily_data[exp_date_obj.strftime('%Y-%m-%d')] += exp['amount']
    
    return render_template('monthly_analytics.html',
                           year_month=year_month,
                           category_data=json.dumps(categories),
                           daily_data=json.dumps(daily_data),
                           monthly_expenses=monthly_expenses)

@app.route('/switch_month', methods=['POST'])
def switch_month():
    direction = request.form.get('direction')
    current_year_month = request.form.get('current_year_month')
    
    try:
        year, month = map(int, current_year_month.split('-'))
        if direction == 'prev':
            if month == 1:
                year -= 1
                month = 12
            else:
                month -= 1
        else:  # next
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
        return redirect(url_for('monthly_analytics', year_month=f"{year}-{month:02d}")) # Format month with leading zero
    except ValueError:
        flash('Invalid month navigation', 'danger')
        return redirect(url_for('analytics'))


# --- NEW FEATURE: Future Spending Projections API Endpoint ---

# Configuration for recurring expenses (customize this)
# In a real app, this would be dynamic, e.g., fetched from user settings or learned.
# 'day_of_month' is included for future more granular logic, not strictly used in current basic projection.
RECURRING_EXPENSES_CONFIG = {
    'Rent': {'amount': 1500.00, 'frequency': 'monthly', 'day_of_month': 15},
    # Add other recurring expenses here, e.g.:
    # 'Netflix': {'amount': 499.00, 'frequency': 'monthly', 'day_of_month': 5},
    # 'Gym Membership': {'amount': 750.00, 'frequency': 'monthly', 'day_of_month': 1},
}

@app.route('/api/spending_projections')
def get_spending_projections():
    num_months_to_project = 6 # Project for the next N months (including current month if relevant)
    
    expenses = session.get('expenses', [])
    
    today = datetime.now()
    
    # --- 1. Calculate historical average for non-recurring expenses ---
    # Look back for the last 6 months of data for average calculation
    historical_window_months = 6 
    
    # Calculate the start date for the historical window (e.g., 6 months ago from the beginning of the current month)
    historical_start_month_dt = today.replace(day=1) - timedelta(days=30 * (historical_window_months - 1)) # Go back N-1 months, then to start of that month
    historical_start_date = historical_start_month_dt.replace(day=1)


    non_recurring_spending_per_month = defaultdict(float)
    months_with_non_recurring_data = set()

    for exp in expenses:
        exp_date = datetime.strptime(exp['date'], '%Y-%m-%d')
        
        # Check if expense is within the historical window and is NOT a configured recurring expense
        if historical_start_date <= exp_date <= today and exp['category'] not in RECURRING_EXPENSES_CONFIG:
            month_year = exp_date.strftime('%Y-%m')
            non_recurring_spending_per_month[month_year] += exp['amount']
            months_with_non_recurring_data.add(month_year) # Track months that actually have non-recurring data

    # Calculate average non-recurring spending per month
    # Divide by the number of months that actually had non-recurring expenses within the window,
    # or by 1 if there was no such data to avoid ZeroDivisionError.
    actual_months_in_window = len(months_with_non_recurring_data)
    avg_monthly_non_recurring = sum(non_recurring_spending_per_month.values()) / max(1, actual_months_in_window)

    # If no historical non-recurring data, assume 0 for projections
    if actual_months_in_window == 0:
        avg_monthly_non_recurring = 0.0


    # --- 2. Project spending for upcoming months ---
    chart_labels = []
    chart_values = []
    
    # Start projection from the current month
    current_projection_month_dt = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    for i in range(num_months_to_project):
        year = current_projection_month_dt.year
        month = current_projection_month_dt.month
        
        projection_month_name = f"{calendar.month_abbr[month]} {year}"
        
        # Start with average non-recurring spending
        projected_amount_for_month = avg_monthly_non_recurring

        # Add recurring expenses for this specific month
        for category, details in RECURRING_EXPENSES_CONFIG.items():
            if details['frequency'] == 'monthly':
                projected_amount_for_month += details['amount']
        
        chart_labels.append(projection_month_name)
        chart_values.append(round(projected_amount_for_month, 2)) # Round for display

        # Move to the next month for the next iteration
        if month == 12:
            current_projection_month_dt = datetime(year + 1, 1, 1)
        else:
            current_projection_month_dt = datetime(year, month + 1, 1)

    # --- 3. Calculate summary projections ---
    # Ensure there are enough projected months before accessing indices
    next_month_projection = chart_values[1] if len(chart_values) > 1 else 0.0
    
    # Average of the next 3 projected months (excluding the current month's projection)
    three_month_avg = 0.0
    if len(chart_values) >= 4: # Need at least current + 3 future months
        three_month_avg = sum(chart_values[1:4]) / 3
    elif len(chart_values) > 1: # If less than 3 future months available (after current), average what's there
        three_month_avg = sum(chart_values[1:]) / (len(chart_values) - 1)


    # Estimated annual projection
    # Take the average of the *first 3 projected months* (including current month) as a base.
    # This provides a more stable annual estimate than just one month.
    annual_estimate_base = sum(chart_values[0:min(len(chart_values), 3)]) / min(len(chart_values), 3) if min(len(chart_values), 3) > 0 else 0.0
    annual_estimate = annual_estimate_base * 12
    
    return jsonify({
        'chart_data': {
            'labels': chart_labels,
            'values': chart_values
        },
        'summary': {
            'next_month': round(next_month_projection, 2),
            'three_month_avg': round(three_month_avg, 2),
            'annual_estimate': round(annual_estimate, 2)
        }
    })


if __name__ == '__main__':
    app.run(debug=True)