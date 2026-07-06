import{j as e,u as P,r as n,a as C,m as o,A as g,L as u}from"./index-BXa_y412.js";function R({onComplete:a}){const[t,r]=n.useState("zoomOut");return n.useEffect(()=>{const i=setTimeout(()=>{r("hold")},400);return()=>clearTimeout(i)},[]),n.useEffect(()=>{if(t==="hold"){const i=setTimeout(()=>{r("zoomIn")},250);return()=>clearTimeout(i)}},[t]),n.useEffect(()=>{if(t==="zoomIn"){const i=setTimeout(()=>{a()},500);return()=>clearTimeout(i)}},[t,a]),e.jsx(o.div,{className:"loader-ln",initial:{opacity:0},animate:{opacity:t==="zoomIn"?0:1},transition:{duration:t==="zoomIn"?.3:.2,ease:[.4,0,.2,1],delay:t==="zoomIn"?.25:0},children:e.jsx("div",{className:"loader-ln-content",children:e.jsxs(o.div,{className:"loader-ln-logo",initial:{scale:50,opacity:0},animate:{scale:t==="zoomOut"||t==="hold"?1:50,opacity:1},transition:{duration:t==="zoomOut"?.4:t==="zoomIn"?.5:.1,ease:[.4,0,.2,1]},children:[e.jsx(o.span,{className:"loader-ln-text-o",initial:{opacity:0},animate:{opacity:1},transition:{duration:.2,delay:.15,ease:[.4,0,.2,1]},children:"O"}),e.jsx(o.span,{className:"loader-ln-text-v",initial:{opacity:0},animate:{opacity:1},transition:{duration:.2,delay:.2,ease:[.4,0,.2,1]},children:"V"})]})})})}function O({onComplete:a}){const[t,r]=n.useState("zoomOut");return n.useEffect(()=>{const i=setTimeout(()=>{r("hold")},400);return()=>clearTimeout(i)},[]),n.useEffect(()=>{if(t==="hold"){const i=setTimeout(()=>{r("zoomIn")},200);return()=>clearTimeout(i)}},[t]),n.useEffect(()=>{if(t==="zoomIn"){const i=setTimeout(()=>{a()},500);return()=>clearTimeout(i)}},[t,a]),e.jsx(o.div,{className:"loader-ln",initial:{opacity:0},animate:{opacity:t==="zoomIn"?0:1},transition:{duration:t==="zoomIn"?.3:.2,ease:[.76,0,.24,1],delay:t==="zoomIn"?.25:0},children:e.jsx("div",{className:"loader-ln-content",children:e.jsxs(o.div,{className:"loader-ln-logo",initial:{scale:50,opacity:0},animate:{scale:t==="zoomOut"||t==="hold"?1:50,opacity:1},transition:{duration:t==="zoomOut"?.4:t==="zoomIn"?.5:.1,ease:[.76,0,.24,1]},children:[e.jsx(o.span,{className:"loader-ln-text-o",initial:{opacity:0},animate:{opacity:1},transition:{duration:.15,delay:.15},children:"O"}),e.jsx(o.span,{className:"loader-ln-text-v",initial:{opacity:0},animate:{opacity:1},transition:{duration:.15,delay:.2},children:"V"})]})})})}const S={privacy:{title:"PRIVACY POLICY",subtitle:"Your privacy matters to us",lastUpdated:"December 1, 2025",sections:[{heading:"Information We Collect",content:`We collect information you provide directly to us, such as when you create an account, use our services, or contact us for support. This may include:
        
• Name and email address
• Usage data and analytics
• Device and browser information
• Location data (with your consent)
• Communication preferences`},{heading:"How We Use Your Information",content:`We use the information we collect to:

• Provide, maintain, and improve our services
• Process transactions and send related information
• Send technical notices and support messages
• Respond to your comments and questions
• Analyze usage patterns to improve user experience
• Protect against fraudulent or illegal activity`},{heading:"Data Security",content:"We implement appropriate technical and organizational measures to protect your personal information against unauthorized access, alteration, disclosure, or destruction. This includes encryption, secure servers, and regular security audits."},{heading:"Your Rights",content:`You have the right to:

• Access your personal data
• Correct inaccurate data
• Request deletion of your data
• Opt-out of marketing communications
• Export your data in a portable format`},{heading:"Contact Us",content:`For any privacy-related questions or concerns, please contact us at:

Email: founders@overhaul.co.in`}]},terms:{title:"TERMS & CONDITIONS",subtitle:"Please read these terms carefully",lastUpdated:"December 1, 2025",sections:[{heading:"Acceptance of Terms",content:"By accessing or using OVERHAUL's services, you agree to be bound by these Terms and Conditions. If you do not agree to these terms, please do not use our services."},{heading:"Use of Services",content:`You agree to use our services only for lawful purposes and in accordance with these Terms. You are responsible for:

• Maintaining the confidentiality of your account
• All activities that occur under your account
• Ensuring your use complies with applicable laws
• Not interfering with the proper functioning of the service`},{heading:"Intellectual Property",content:"All content, features, and functionality of OVERHAUL are owned by us and are protected by international copyright, trademark, and other intellectual property laws. You may not reproduce, distribute, or create derivative works without our express permission."},{heading:"Limitation of Liability",content:"OVERHAUL shall not be liable for any indirect, incidental, special, consequential, or punitive damages resulting from your use of or inability to use the service. Our total liability shall not exceed the amount paid by you in the past 12 months."},{heading:"Modifications",content:"We reserve the right to modify these terms at any time. We will notify users of significant changes via email or through our platform. Continued use after changes constitutes acceptance of the new terms."},{heading:"Governing Law",content:"These Terms shall be governed by and construed in accordance with the laws of India, without regard to its conflict of law provisions."}]},refunds:{title:"CANCELLATION & REFUNDS",subtitle:"Our refund policy",lastUpdated:"December 1, 2025",sections:[{heading:"Cancellation Policy",content:`You may cancel your subscription at any time through your account settings or by contacting our support team. Upon cancellation:

• Your subscription will remain active until the end of the current billing period
• You will not be charged for subsequent billing periods
• Access to premium features will end when your current period expires`},{heading:"Refund Eligibility",content:`We offer refunds under the following conditions:

• Full refund within 7 days of initial purchase if service is unused
• Prorated refund for annual subscriptions within 30 days
• Full refund if service is unavailable for more than 72 consecutive hours
• Case-by-case consideration for exceptional circumstances`},{heading:"Non-Refundable Items",content:`The following are non-refundable:

• Consumed API credits or usage
• Custom development or consultation services
• Subscriptions cancelled after the refund period
• Accounts terminated due to policy violations`},{heading:"Refund Process",content:`To request a refund:

1. Contact us at founders@overhaul.co.in
2. Provide your account email and reason for refund
3. We will review your request within 3-5 business days
4. Approved refunds will be processed within 7-10 business days
5. Refunds will be credited to the original payment method`},{heading:"Disputes",content:"If you have any disputes regarding charges or refunds, please contact our support team before initiating a chargeback with your payment provider. We are committed to resolving issues amicably."}]},shipping:{title:"SHIPPING POLICY",subtitle:"Digital delivery information",lastUpdated:"December 1, 2025",sections:[{heading:"Digital Products",content:`OVERHAUL is a digital platform providing software-as-a-service (SaaS) solutions. As such:

• All products and services are delivered digitally
• No physical shipping is required
• Access is granted immediately upon successful payment
• Login credentials are sent to your registered email`},{heading:"Access Delivery",content:`Upon successful subscription or purchase:

• You will receive a confirmation email within minutes
• Access to the platform is immediate
• API keys (if applicable) are generated instantly
• Documentation and guides are available online`},{heading:"Delivery Issues",content:`If you experience any issues accessing your purchase:

• Check your spam/junk folder for confirmation emails
• Ensure you're using the correct login credentials
• Clear your browser cache and try again
• Contact support at founders@overhaul.co.in`},{heading:"International Access",content:`OVERHAUL services are available globally. However:

• Some features may vary by region due to regulatory requirements
• Payment processing may vary based on your location
• Support response times may vary based on time zones`}]}};function h({type:a}){const r=P().state?.skipLoader||!1,[i,E]=n.useState(!r),[d,v]=n.useState(!1),[N,x]=n.useState(!1),[T,b]=n.useState(null),I=C(),y=n.useRef(null),f=n.useRef({x:0,y:0}),m=n.useRef(null),p=S[a],w=a==="privacy"?"Privacy Policy":a==="terms"?"Terms & Conditions":a==="refunds"?"Cancellation & Refunds":"Shipping Policy";n.useEffect(()=>{window.history.pushState({skipLoader:!0},"",window.location.href);const s=l=>{v(!0),b("/")};return window.addEventListener("popstate",s),()=>{window.removeEventListener("popstate",s)}},[]),n.useEffect(()=>{document.title=`OVERHAUL | ${w}`},[w]);const j=s=>{s.preventDefault(),v(!0),b("/")},L=()=>{I(T||"/",{state:{skipLoader:!0}})};return n.useEffect(()=>{const s=()=>{y.current&&(y.current.style.transform=`translate3d(${f.current.x}px, ${f.current.y}px, 0) translate(-50%, -50%)`),m.current=requestAnimationFrame(s)};m.current=requestAnimationFrame(s);const l=c=>{f.current={x:c.clientX,y:c.clientY}};return window.addEventListener("mousemove",l,{passive:!0}),()=>{m.current&&cancelAnimationFrame(m.current),window.removeEventListener("mousemove",l)}},[]),n.useEffect(()=>{!i&&!d&&(()=>{document.querySelectorAll("a, button, .magnetic-btn").forEach(c=>{c.addEventListener("mouseenter",()=>x(!0)),c.addEventListener("mouseleave",()=>x(!1))})})()},[i,d]),e.jsxs(e.Fragment,{children:[e.jsx("div",{ref:y,className:`cursor ${N?"hovering":""}`}),e.jsx("div",{className:"moving-bg",children:e.jsx("svg",{className:"moving-bg-svg",viewBox:"0 0 1000 1000",preserveAspectRatio:"none",children:e.jsx(o.path,{d:"M0,500 Q250,400 500,500 T1000,500",stroke:"rgba(204, 255, 0, 0.1)",strokeWidth:"2",fill:"none",animate:{d:["M0,500 Q250,400 500,500 T1000,500","M0,500 Q250,600 500,500 T1000,500","M0,500 Q250,400 500,500 T1000,500"]},transition:{duration:8,repeat:1/0,ease:"easeInOut"}})})}),e.jsx(g,{mode:"wait",children:i&&e.jsx(R,{onComplete:()=>E(!1)},"entry-loader")}),e.jsx(g,{mode:"wait",children:d&&e.jsx(O,{onComplete:L},"exit-loader")}),e.jsx(g,{children:!i&&!d&&e.jsxs(o.div,{className:"policy-page",initial:{opacity:0},animate:{opacity:1},exit:{opacity:0},transition:{duration:.4},children:[e.jsxs("nav",{className:"contact-nav",children:[e.jsx("a",{href:"/",onClick:j,className:"nav-logo",children:"OVERHAUL™"}),e.jsx("a",{href:"/",onClick:j,className:"back-btn",children:"← BACK TO HOME"})]}),e.jsxs("div",{className:"policy-content",children:[e.jsxs(o.div,{className:"policy-header",initial:{opacity:0,y:50},animate:{opacity:1,y:0},transition:{delay:.1,duration:.6},children:[e.jsx("span",{className:"contact-label",children:"LEGAL"}),e.jsx("h1",{className:"policy-title",children:p.title}),e.jsx("p",{className:"policy-subtitle",children:p.subtitle}),e.jsxs("p",{className:"policy-date",children:["Last updated: ",p.lastUpdated]})]}),e.jsx(o.div,{className:"policy-sections",initial:{opacity:0,y:30},animate:{opacity:1,y:0},transition:{delay:.2,duration:.6},children:p.sections.map((s,l)=>e.jsxs("div",{className:"policy-section",children:[e.jsx("h2",{className:"policy-section-heading",children:s.heading}),e.jsx("div",{className:"policy-section-content",children:s.content.split(`
`).map((c,A)=>e.jsx("p",{children:c},A))})]},l))}),e.jsxs(o.div,{className:"policy-links",initial:{opacity:0,y:30},animate:{opacity:1,y:0},transition:{delay:.3,duration:.6},children:[e.jsx("h3",{children:"Other Policies"}),e.jsxs("div",{className:"policy-links-grid",children:[a!=="privacy"&&e.jsx(u,{to:"/privacy",children:"Privacy Policy"}),a!=="terms"&&e.jsx(u,{to:"/terms",children:"Terms & Conditions"}),a!=="refunds"&&e.jsx(u,{to:"/refunds",children:"Cancellation & Refunds"}),a!=="shipping"&&e.jsx(u,{to:"/shipping",children:"Shipping Policy"}),e.jsx(u,{to:"/contact",children:"Contact Us"})]})]})]}),e.jsx("footer",{className:"contact-footer",children:e.jsx("span",{children:"© 2025 OVERHAUL. ALL RIGHTS RESERVED."})})]})})]})}function U(){return e.jsx(h,{type:"privacy"})}function k(){return e.jsx(h,{type:"terms"})}function H(){return e.jsx(h,{type:"refunds"})}function D(){return e.jsx(h,{type:"shipping"})}export{U as PrivacyPolicy,H as RefundsPolicy,D as ShippingPolicy,k as TermsConditions};
