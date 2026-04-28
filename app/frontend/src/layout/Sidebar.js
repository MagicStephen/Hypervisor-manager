import React from 'react';
import { Container } from 'react-bootstrap';
import Button from '../components/button';
import Icon from '../components/Icon';

function AppSidebar() {
  return (
    <Container className='d-flex flex-column h-100 bg-light py-2' style={{width:'100px',minWidth:'100px'}}>
        <div className="text-center" title="Virtual Platform Manager">
            <strong>VPM</strong>
        </div>
        <hr className='my-2'/>
        <ul className="sidebar-nav list-unstyled px-1">
            <li>
                <Button
                    className="btn-primary w-100 px-2" 
                    tooltip="Performance overview"
                >
                <Icon name="trendChart" size="2x" />
                </Button>  
            </li>
            <li className=' mt-2'>
                <Button
                    className="btn-primary w-100 px-2" 
                    tooltip="Server Management"
                >
                <Icon name="server" size="2x" />
                </Button>  
            </li>
        </ul>     
    </Container>
  );
}

export default AppSidebar;