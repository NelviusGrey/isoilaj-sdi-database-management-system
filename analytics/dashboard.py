
"""Advanced analytics dashboard"""
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

class AnalyticsDashboard:
    def __init__(self, cg_df, ch_df):
        self.cg_df = cg_df
        self.ch_df = ch_df
    
    def create_overview_dashboard(self):
        """Create comprehensive overview dashboard"""
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Gender Distribution', 'Age Groups', 
                          'Education Levels', 'Zonal Leaders'),
            specs=[[{"type": "pie"}, {"type": "bar"}],
                   [{"type": "bar"}, {"type": "bar"}]]
        )
        
        # Gender distribution pie chart
        if not self.cg_df.empty and 'gender' in self.cg_df.columns:
            gender_counts = self.cg_df['gender'].value_counts()
            fig.add_trace(
                go.Pie(labels=gender_counts.index, values=gender_counts.values,
                       name="Gender"),
                row=1, col=1
            )
        
        # Age groups bar chart
        if not self.cg_df.empty and 'age' in self.cg_df.columns:
            age_groups = self._create_age_groups(self.cg_df['age'])
            age_counts = age_groups.value_counts()
            fig.add_trace(
                go.Bar(x=age_counts.index, y=age_counts.values,
                       name="Age Groups"),
                row=1, col=2
            )
        
        fig.update_layout(height=600, showlegend=False)
        return fig
    
    def create_trend_analysis(self):
        """Create trend analysis charts"""
        # Registration trends over time
        if 'last_updated' in self.cg_df.columns:
            self.cg_df['registration_date'] = pd.to_datetime(self.cg_df['last_updated']).dt.date
            daily_registrations = self.cg_df.groupby('registration_date').size().reset_index()
            daily_registrations.columns = ['Date', 'Registrations']
            
            fig = px.line(daily_registrations, x='Date', y='Registrations',
                         title='Daily Registration Trends')
            return fig
        return None
    
    def _create_age_groups(self, ages):
        """Helper method to create age groups"""
        if ages.empty:
            return pd.Series([], dtype='object')
        return pd.cut(ages, bins=[0, 18, 35, 50, 100], 
                     labels=['0-18', '19-35', '36-50', '50+'])
